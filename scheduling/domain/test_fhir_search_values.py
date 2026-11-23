"""Section 15.5: a search value: "either" by comma, closed code lists, NUL characters."""

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_bundle import page_links
from scheduling.domain.fhir_declaration import ResourceDeclaration, declaration_for
from scheduling.domain.fhir_search import SearchQuery, parse_search, split_alternatives


def _declared(name: str) -> ResourceDeclaration:
    found = declaration_for(name)
    assert found is not None
    return found


ORGANIZATION = _declared("Organization")
ROLE = _declared("PractitionerRole")


def _parse(declaration: ResourceDeclaration, **params: str) -> Result[SearchQuery]:
    return parse_search(declaration, {name: [value] for name, value in params.items()})


def _query(**changes: object) -> SearchQuery:
    base = SearchQuery((), 20, 0, "name", False, ())
    return SearchQuery(**{**base.__dict__, **changes})


APPOINTMENT = _declared("Appointment")


def _filters(result: Result[SearchQuery]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    assert isinstance(result, Success)
    return result.value.filters


def returns_each_alternative_when_a_code_has_a_comma() -> None:
    result = _parse(APPOINTMENT, status="booked,cancelled")

    assert _filters(result) == (("status", ("booked", "cancelled")),)


def returns_refusal_listing_the_codes_when_a_code_is_outside_the_list() -> None:
    result = _parse(APPOINTMENT, status="booked,nonsense")

    assert result == Failure.invalid_input(
        [
            FieldMessage(
                "status",
                "Use one of: booked, checked-in, fulfilled, cancelled, noshow, waitlist, "
                "proposed, pending.",
            )
        ]
    )


def returns_refusal_when_one_alternative_is_empty() -> None:
    assert _parse(APPOINTMENT, status="booked,") == Failure.invalid_input(
        [FieldMessage("status", "The value cannot be read.")]
    )


def returns_each_repeat_as_its_own_filter_when_a_parameter_is_repeated() -> None:
    result = parse_search(APPOINTMENT, {"date": ["ge2026-11-23", "lt2026-11-24"]})

    assert _filters(result) == (("date", ("ge2026-11-23",)), ("date", ("lt2026-11-24",)))


def returns_whole_date_when_the_date_has_a_comma() -> None:
    assert _parse(APPOINTMENT, date="2026-11-23,2026-11-24") == Failure.invalid_input(
        [FieldMessage("date", "The value cannot be read.")]
    )


@pytest.mark.parametrize("value", ["a\x00b", "\x00"])
def returns_refusal_naming_the_parameter_when_a_value_holds_a_nul_character(value: str) -> None:
    assert _parse(ORGANIZATION, name=value) == Failure.invalid_input(
        [FieldMessage("name", "The value cannot be read.")]
    )


def returns_refusal_when_only_a_repeat_holds_a_nul_character() -> None:
    result = parse_search(APPOINTMENT, {"date": ["ge2026-11-23", "lt2026-11\x00"]})

    assert isinstance(result, Failure)
    assert result.details == {"fields": [{"field": "date", "message": "The value cannot be read."}]}


def returns_refusal_when_a_flag_is_not_true_or_false() -> None:
    assert _parse(ORGANIZATION, active="yes") == Failure.invalid_input(
        [FieldMessage("active", "The value cannot be read.")]
    )


def returns_refusal_when_a_reference_is_not_an_id() -> None:
    assert isinstance(_parse(ROLE, practitioner="not-an-id"), Failure)


def returns_refusal_when_a_code_is_empty_or_longer_than_the_maximum() -> None:
    assert isinstance(_parse(ROLE, specialty=" "), Failure)
    assert isinstance(_parse(ROLE, specialty="x" * 101), Failure)
    assert isinstance(_parse(ROLE, specialty="x" * 100), Success)


def returns_the_alternatives_joined_by_a_comma_in_every_link() -> None:
    query = _query(filters=(("status", ("booked", "cancelled")),))

    url = str(page_links("a", query, 1)[0]["url"])

    assert url == "a?status=booked%2Ccancelled&_count=20&_offset=0&_sort=name"


@pytest.mark.parametrize(
    ("value", "pieces"),
    [
        ("a,b", ["a", "b"]),
        ("a\\,b", ["a,b"]),
        ("a\\\\,b", ["a\\", "b"]),
        ("a\\\\\\,b", ["a\\,b"]),
        ("a\\b", ["a\\b"]),
        ("a\\", ["a\\"]),
        ("", [""]),
        (",", ["", ""]),
    ],
)
def returns_the_alternatives_with_fhir_escapes_read(value: str, pieces: list[str]) -> None:
    assert split_alternatives(value) == pieces
