"""Sections 15.1, 15.5: reading a search against the declaration, bundles and outcomes."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from scheduling.domain.failure import Failure, FailureCode, Result, Success
from scheduling.domain.fhir_bundle import page_links, search_bundle
from scheduling.domain.fhir_capability import capability_statement
from scheduling.domain.fhir_common import Resource, fhir_instant
from scheduling.domain.fhir_declaration import FHIR_RESOURCES, ResourceDeclaration, declaration_for
from scheduling.domain.fhir_near import NearPoint, is_within, parse_near
from scheduling.domain.fhir_outcome import failure_outcome, operation_outcome
from scheduling.domain.fhir_search import SearchQuery, parse_id, parse_search


def _declared(name: str) -> ResourceDeclaration:
    found = declaration_for(name)
    assert found is not None
    return found


ORGANIZATION = _declared("Organization")
ROLE = _declared("PractitionerRole")
LOCATION = _declared("Location")
SOME_ID = "11111111-1111-1111-1111-111111111111"


def _parse(declaration: ResourceDeclaration, **params: str) -> Result[SearchQuery]:
    return parse_search(declaration, {name: [value] for name, value in params.items()})


def _query(**changes: object) -> SearchQuery:
    base = SearchQuery((), 20, 0, "name", False, ())
    return SearchQuery(**{**base.__dict__, **changes})


def returns_defaults_when_no_parameter_given() -> None:
    assert _parse(ORGANIZATION) == Success(_query())


def returns_each_read_value_when_parameters_are_valid() -> None:
    result = _parse(
        ORGANIZATION, _count="100", _offset="40", _sort="-active", active="true", name=" Riv "
    )

    assert result == Success(
        _query(
            count=100, offset=40, sort="active", descending=True,
            filters=(("active", ("true",)), ("name", ("Riv",))),
        )
    )  # fmt: skip


def returns_zero_count_and_offset_bounds_when_at_the_edge() -> None:
    assert _parse(ORGANIZATION, _count="0") == Success(_query(count=0))
    assert _parse(ORGANIZATION, _offset="1000000") == Success(_query(offset=1_000_000))


def _refused_name(result: object) -> str:
    assert isinstance(result, Failure)
    assert result.code is FailureCode.INVALID_INPUT
    return str(result.details["fields"][0]["field"])  # type: ignore[index]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("_count", "101"),
        ("_count", "-1"),
        ("_count", "x"),
        ("_count", ""),
        ("_count", "٣"),
        ("_offset", "1000001"),
        ("_offset", "-1"),
        ("_sort", "colour"),
        ("_sort", "--name"),
        ("_sort", ""),
        ("_format", "xml"),
        ("_include", "PractitionerRole:practitioner"),
        ("active", "True"),
        ("active", ""),
        ("name", "   "),
        ("name", "x" * 101),
        ("colour", "red"),
        ("_id", "1"),
        ("partof", "not-an-id"),
    ],
)
def returns_failure_naming_parameter_when_value_is_refused(name: str, value: str) -> None:
    assert _refused_name(_parse(ORGANIZATION, **{name: value})) == name


def returns_failure_when_parameter_given_twice() -> None:
    result = parse_search(ORGANIZATION, {"name": ["a", "b"]})

    assert _refused_name(result) == "name"


def returns_failure_when_parameter_given_with_no_value() -> None:
    assert _refused_name(parse_search(ORGANIZATION, {"name": []})) == "name"


def returns_include_when_declared_for_the_resource() -> None:
    result = _parse(ROLE, _include="PractitionerRole:organization", _format="json")

    assert result == Success(_query(sort="", include=("PractitionerRole:organization",)))


def returns_failure_when_sort_is_not_a_parameter_of_resource() -> None:
    assert _refused_name(_parse(_declared("Practitioner"), _sort="address-city")) == "_sort"


def returns_lowercase_canonical_id_when_reference_has_resource_prefix() -> None:
    result = _parse(ROLE, practitioner=f"Practitioner/{SOME_ID.upper()}")

    assert result == Success(_query(sort="", filters=(("practitioner", (SOME_ID,)),)))


def returns_last_part_when_code_has_system_prefix() -> None:
    result = _parse(ROLE, specialty="http://x|cardio")

    assert isinstance(result, Success)
    assert result.value.filters == (("specialty", ("cardio",)),)


def returns_near_value_unchanged_when_readable() -> None:
    result = _parse(LOCATION, near="52.5|13.4|5|km")

    assert isinstance(result, Success)
    assert result.value.filters == (("near", ("52.5|13.4|5|km",)),)


def returns_canonical_id_or_none_when_id_parsed() -> None:
    assert parse_id(SOME_ID.upper()) == SOME_ID
    assert parse_id("1" * 32) == SOME_ID
    assert parse_id("not-an-id") is None
    assert parse_id(SOME_ID + "-") is None
    assert parse_id(SOME_ID + "-----") is None


def returns_point_when_near_is_valid_in_either_unit() -> None:
    assert parse_near("52.5|13.4|5|km") == NearPoint(52.5, 13.4, 5.0)
    miles = parse_near("0|0|1|[mi_i]")
    assert miles is not None
    assert miles.kilometres == pytest.approx(1.609344)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "1|2|3",
        "1|2|3|km|x",
        "1|2|3|m",
        "a|2|3|km",
        "91|0|1|km",
        "-91|0|1|km",
        "0|181|1|km",
        "0|-181|1|km",
        "0|0|-1|km",
        "0|0|1000.1|km",
        "0|0|1000|[mi_i]",
        "nan|0|1|km",
    ],
)
def returns_none_when_near_cannot_be_read(text: str) -> None:
    assert parse_near(text) is None


def returns_point_when_near_is_exactly_at_the_limits() -> None:
    assert parse_near("90|180|1000|km") == NearPoint(90.0, 180.0, 1000.0)
    assert parse_near("-90|-180|0|km") == NearPoint(-90.0, -180.0, 0.0)


def returns_true_only_when_site_is_within_distance() -> None:
    berlin = NearPoint(52.52, 13.405, 10.0)

    assert is_within(berlin, 52.52, 13.405)
    assert is_within(berlin, 52.55, 13.45)
    assert not is_within(berlin, 52.52, 13.60)
    assert not is_within(berlin, 48.14, 11.58)
    assert is_within(NearPoint(0, 0, 111.2), 1.0, 0.0) is True
    assert is_within(NearPoint(0, 0, 111.1), 1.0, 0.0) is False
    assert is_within(NearPoint(0, 0, 111.2), 0.0, 1.0) is True
    assert is_within(NearPoint(0, 0, 111.1), 0.0, 1.0) is False


def returns_only_self_link_when_everything_fits_one_page() -> None:
    links = page_links("http://h/fhir/Organization", _query(), 3)

    assert links == [
        {
            "relation": "self",
            "url": "http://h/fhir/Organization?_count=20&_offset=0&_sort=name",
        }
    ]


def returns_next_link_when_more_rows_remain() -> None:
    links = page_links("http://h/fhir/Organization", _query(count=10), 21)

    assert [link["relation"] for link in links] == ["self", "next"]
    assert links[1]["url"].endswith("_count=10&_offset=10&_sort=name")  # type: ignore[attr-defined]


def returns_no_next_link_when_last_row_is_on_this_page() -> None:
    assert len(page_links("a", _query(count=10), 10)) == 1
    assert len(page_links("a", _query(count=10, offset=10), 20)) == 2
    assert len(page_links("a", _query(count=10, offset=10), 21)) == 3


def returns_no_next_link_when_count_is_zero() -> None:
    assert [item["relation"] for item in page_links("a", _query(count=0), 5)] == ["self"]


def returns_previous_link_one_page_back_but_never_below_zero() -> None:
    middle = page_links("a", _query(count=10, offset=30), 100)
    first = page_links("a", _query(count=10, offset=5), 100)

    assert "_offset=10&" in str(middle[-1]["url"])
    assert middle[-1]["relation"] == "previous"
    assert "_offset=0&" in str(first[-1]["url"])


def returns_filters_include_and_descending_sort_in_every_link() -> None:
    query = _query(
        filters=(("name", ("A B",)),), sort="active", descending=True,
        include=("PractitionerRole:organization",),
    )  # fmt: skip

    url = str(page_links("a", query, 1)[0]["url"])

    assert url == (
        "a?name=A+B&_count=20&_offset=0&_sort=-active&_include=PractitionerRole%3Aorganization"
    )


def returns_matches_then_includes_with_modes_when_bundle_built() -> None:
    match: Resource = {"resourceType": "PractitionerRole", "id": "1"}
    included: Resource = {"resourceType": "Practitioner", "id": "2"}

    bundle = search_bundle(
        service_base="http://h/fhir", resource_type="PractitionerRole", query=_query(),
        total=1, matches=[match], included=[included],
    )  # fmt: skip

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"
    assert bundle["total"] == 1
    assert bundle["entry"] == [
        {
            "fullUrl": "http://h/fhir/PractitionerRole/1",
            "resource": match,
            "search": {"mode": "match"},
        },
        {
            "fullUrl": "http://h/fhir/Practitioner/2",
            "resource": included,
            "search": {"mode": "include"},
        },
    ]
    assert str(bundle["link"][0]["url"]).startswith("http://h/fhir/PractitionerRole?")  # type: ignore[index]


def returns_every_declared_resource_with_its_parameters_when_capability_built() -> None:
    body = capability_statement(FHIR_RESOURCES)

    assert body["fhirVersion"] == "4.0.1"
    assert body["kind"] == "instance"
    assert body["format"] == ["application/fhir+json"]
    resources = body["rest"][0]["resource"]  # type: ignore[index]
    assert [item["type"] for item in resources] == [item.type for item in FHIR_RESOURCES]
    role = next(item for item in resources if item["type"] == "PractitionerRole")
    assert [item["code"] for item in role["interaction"]] == [
        "read",
        "search-type",
        "create",
        "update",
        "delete",
    ]
    assert role["versioning"] == "versioned"
    assert role["searchInclude"] == list(ROLE.includes)
    assert {"name": "active", "type": "token"} in role["searchParam"]
    assert {"name": "practitioner", "type": "reference"} in role["searchParam"]
    location = next(item for item in resources if item["type"] == "Location")
    assert {"name": "near", "type": "special"} in location["searchParam"]
    assert {"name": "name", "type": "string"} in location["searchParam"]
    organization = next(item for item in resources if item["type"] == "Organization")
    assert "searchInclude" not in organization
    code_system = next(item for item in resources if item["type"] == "CodeSystem")
    assert code_system["searchParam"] == []


def returns_sortable_parameters_in_fixed_order_when_declared() -> None:
    assert ORGANIZATION.sortable == ("name", "address-city", "active")
    assert _declared("CodeSystem").sortable == ()
    assert declaration_for("Nothing") is None
    assert _declared("CodeSystem").single_id == "specialty"


def returns_issue_with_fixed_text_and_expression_when_outcome_built() -> None:
    assert operation_outcome("invalid", "Bad.", "cid", ("name",)) == {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {"text": "Bad."},
                "diagnostics": "cid",
                "expression": ["name"],
            }
        ],
    }
    assert "expression" not in operation_outcome("x", "t", "c")["issue"][0]  # type: ignore[index]


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (Failure.not_found(), "not-found"),
        (Failure.unauthenticated(), "login"),
        (Failure.forbidden(), "forbidden"),
        (Failure.rate_limited(), "throttled"),
        (Failure.invalid_input([]), "invalid"),
        (Failure.conflict(["x"]), "conflict"),
    ],
)
def returns_issue_code_of_failure_when_failure_is_an_outcome(failure: Failure, code: str) -> None:
    assert failure_outcome(failure, "Text.", "cid")["issue"][0]["code"] == code  # type: ignore[index]


def returns_named_fields_only_when_failure_has_readable_fields() -> None:
    named = Failure(FailureCode.INVALID_INPUT, {"fields": [{"field": "a"}, {"x": 1}, "b"]})
    odd = Failure(FailureCode.INVALID_INPUT, {"fields": "a"})

    assert failure_outcome(named, "t", "c")["issue"][0]["expression"] == ["a"]  # type: ignore[index]
    assert "expression" not in failure_outcome(odd, "t", "c")["issue"][0]  # type: ignore[index]


def returns_utc_millisecond_instant_when_moment_has_another_zone() -> None:
    from datetime import timedelta, timezone

    moment = datetime(2026, 1, 2, 4, 5, 6, 789999, tzinfo=timezone(timedelta(hours=2)))

    assert fhir_instant(moment) == "2026-01-02T02:05:06.789Z"
    assert UUID(SOME_ID)


def _refused_message(result: object) -> str:
    assert isinstance(result, Failure)
    return str(result.details["fields"][0]["message"])  # type: ignore[index]


def returns_reason_in_words_when_a_parameter_is_refused() -> None:
    assert _refused_message(parse_search(ORGANIZATION, {"name": ["a", "b"]})) == (
        "A parameter may be given once."
    )
    assert _refused_message(_parse(ORGANIZATION, colour="red")) == (
        "This search parameter is not supported."
    )
    assert _refused_message(_parse(ORGANIZATION, active="maybe")) == "The value cannot be read."


def returns_offset_zero_when_offset_is_given_as_zero() -> None:
    assert _parse(ORGANIZATION, _offset="0") == Success(_query(offset=0))


def returns_false_filter_when_flag_is_false() -> None:
    assert _parse(ORGANIZATION, active="false") == Success(
        _query(filters=(("active", ("false",)),))
    )


def returns_refusal_when_near_value_is_unreadable() -> None:
    assert _refused_name(_parse(LOCATION, near="bad")) == "near"


def returns_last_segment_when_reference_is_a_full_address() -> None:
    result = _parse(ROLE, practitioner=f"http://h/fhir/Practitioner/{SOME_ID}")

    assert result == Success(_query(sort="", filters=(("practitioner", (SOME_ID,)),)))


def returns_whole_text_when_text_parameter_holds_a_bar() -> None:
    assert _parse(ORGANIZATION, name="a|b|c") == Success(_query(filters=(("name", ("a|b|c",)),)))


def returns_last_part_of_code_whatever_the_system_prefix() -> None:
    assert _parse(ROLE, specialty="x|y|cardio") == Success(
        _query(sort="", filters=(("specialty", ("cardio",)),))
    )
    assert _parse(ROLE, specialty="cardio") == Success(
        _query(sort="", filters=(("specialty", ("cardio",)),))
    )


def returns_value_when_text_is_one_or_one_hundred_characters() -> None:
    assert _parse(ORGANIZATION, name="a") == Success(_query(filters=(("name", ("a",)),)))
    hundred = "x" * 100
    assert _parse(ORGANIZATION, name=hundred) == Success(_query(filters=(("name", (hundred,)),)))


def returns_within_when_distance_is_exactly_zero() -> None:
    assert is_within(NearPoint(10.0, 10.0, 0.0), 10.0, 10.0)


def returns_longitude_distance_scaled_by_both_latitudes_when_far_from_equator() -> None:
    point = NearPoint(60.0, 0.0, 60.0)

    assert is_within(point, 60.0, 1.0)
    assert not is_within(NearPoint(60.0, 0.0, 50.0), 60.0, 1.0)


def returns_previous_when_offset_is_one() -> None:
    links = page_links("a", _query(count=10, offset=1), 50)

    assert [item["relation"] for item in links] == ["self", "next", "previous"]
    assert links[1]["url"] == "a?_count=10&_offset=11&_sort=name"
    assert links[2]["url"] == "a?_count=10&_offset=0&_sort=name"


def returns_capability_header_fields_when_statement_built() -> None:
    body = capability_statement(())

    assert body == {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2026-11-22",
        "description": "DrLibre appointment scheduling, FHIR R4 API.",
        "kind": "instance",
        "implementation": {
            "description": "DrLibre appointment scheduling, FHIR R4 API.",
            "url": "https://drlibre.example/fhir",
        },
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json"],
        "rest": [{"mode": "server", "resource": []}],
    }


def returns_text_and_correlation_id_when_failure_is_an_outcome() -> None:
    issue = failure_outcome(Failure.not_found(), "Gone.", "cid-9")["issue"][0]  # type: ignore[index]

    assert (issue["details"], issue["diagnostics"]) == ({"text": "Gone."}, "cid-9")


def returns_utc_instant_whatever_the_machine_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    try:
        moment = datetime(2026, 1, 2, 3, 4, 5, 6000, tzinfo=UTC)
        assert fhir_instant(moment) == "2026-01-02T03:04:05.006Z"
    finally:
        monkeypatch.undo()
        time.tzset()
