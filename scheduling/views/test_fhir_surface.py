"""Task 24d, spec 15.2, 15.4, 15.5: section 15 as data (`fhir_spec_tables`) against the
CapabilityStatement and the running routes, both ways: what the spec names is served, nothing
else is. A difference from the letter needs an ADR that says so."""

from pathlib import Path
from uuid import uuid4

import pytest

from scheduling.views.fhir_spec_tables import (
    ADMIN,
    ADR_ADDITIONS,
    INTERACTIONS,
    PUBLIC,
    ROLES,
    SPEC_RESOURCES,
    SpecResource,
)
from scheduling.views.fhir_test_support import FHIR_JSON, client_for, get, token_of

pytestmark = pytest.mark.django_db

ADR_FOLDER = Path(__file__).resolve().parents[2] / "doc" / "adr"
BY_TYPE = [pytest.param(item, id=item.type) for item in SPEC_RESOURCES]
ABSENT_ID = str(uuid4())
BODY_DECIDES = ("Schedule", "Patient", "Appointment", "AppointmentResponse")
REFUSED_FOR_ROLE = {PUBLIC: 401, "patient": 403, "clinician": 403, ADMIN: 403}
HTTP_METHOD = {"read": "get", "search-type": "get", "create": "post", "update": "put"}


def _served(spec: SpecResource) -> set[str]:
    named = {"read", "search-type", *spec.writers}
    dropped = {item.interaction for item in spec.differences if item.kind == "missing"}
    added = {item.interaction for item in spec.differences if item.kind == "extra"}
    return (named - dropped) | added


def _allowed_roles(spec: SpecResource, interaction: str) -> tuple[str, ...]:
    if interaction in ("read", "search-type"):
        return spec.readers
    return spec.writers.get(interaction, (ADMIN,))


def _refusal_codes(spec: SpecResource, interaction: str, role: str) -> tuple[int, ...]:
    """What a role that may not use the interaction is answered. A scoped difference is 200; where
    the body names the record that decides the rights, an empty body is 400 before any refusal."""
    if any(item.role == role and item.interaction == interaction for item in spec.differences):
        return (200,)
    refused = REFUSED_FOR_ROLE[role]
    deciding = spec.type in BODY_DECIDES and interaction in ("create", "update") and role != PUBLIC
    return (refused, 400) if deciding else (refused,)


def _shut_codes(interaction: str) -> tuple[int, ...]:
    """Own-record rules answer 403 for an absent id, so only searches and creates must not."""
    return (401, 403, 405) if interaction in ("search-type", "create") else (401, 405)


def _call(interaction: str, spec: SpecResource, token: str | None) -> int:
    client = client_for(token)
    path = f"/fhir/{spec.type}"
    if interaction in ("read", "update", "delete"):
        path = f"{path}/{ABSENT_ID}"
    call = getattr(client, HTTP_METHOD.get(interaction, "delete"))
    if interaction in ("create", "update"):
        return int(call(path, data="{}", content_type=FHIR_JSON).status_code)
    return int(call(path).status_code)


def _adr_text(number: str, quote: str) -> bool:
    files = list(ADR_FOLDER.glob(f"{number}-*.md"))
    return bool(files) and quote.lower() in " ".join(files[0].read_text().split()).lower()


@pytest.fixture
def tokens() -> dict[str, str | None]:
    return {PUBLIC: None, **{role: token_of(role=role.upper()) for role in ROLES[1:]}}


def _parameters_served(spec: SpecResource) -> set[str]:
    added = {item.parameter for item in ADR_ADDITIONS if item.resource == spec.type}
    return set(spec.parameters) | added


def returns_every_resource_interaction_and_parameter_of_the_spec_in_the_capability_statement() -> (
    None
):
    response = get("/fhir/metadata")

    served = {item["type"]: item for item in response.json()["rest"][0]["resource"]}
    assert sorted(served) == sorted(item.type for item in SPEC_RESOURCES)
    for spec in SPEC_RESOURCES:
        entry = served[spec.type]
        assert {item["code"] for item in entry["interaction"]} == _served(spec), spec.type
        assert {item["name"] for item in entry.get("searchParam", [])} == _parameters_served(
            spec
        ), spec.type
        assert set(entry.get("searchInclude", [])) == set(spec.includes), spec.type


@pytest.mark.parametrize("spec", BY_TYPE)
def returns_405_for_every_interaction_the_spec_does_not_name(spec: SpecResource) -> None:
    token = token_of(role="ADMIN")
    unserved = [item for item in INTERACTIONS if item not in _served(spec)]

    answers = {item: _call(item, spec, token) for item in unserved}

    assert answers == {item: 405 for item in unserved}


@pytest.mark.parametrize("spec", BY_TYPE)
def returns_access_of_section_15_4_for_every_role_on_every_named_interaction(
    spec: SpecResource, tokens: dict[str, str | None]
) -> None:
    answers = {
        (item, role): _call(item, spec, tokens[role])
        for item in sorted(_served(spec))
        for role in ROLES
    }

    wrongly_open = {
        key: code
        for key, code in answers.items()
        if key[1] not in _allowed_roles(spec, key[0]) and code not in _refusal_codes(spec, *key)
    }
    wrongly_shut = {
        key: code
        for key, code in answers.items()
        if key[1] in _allowed_roles(spec, key[0]) and code in _shut_codes(key[0])
    }
    assert wrongly_open == {}
    assert wrongly_shut == {}


@pytest.mark.parametrize("spec", BY_TYPE)
def returns_400_naming_the_parameter_when_a_search_parameter_is_not_in_the_spec(
    spec: SpecResource,
) -> None:
    response = get(f"/fhir/{spec.type}?not-in-the-spec=1", token_of(role="ADMIN"))

    assert response.status_code == 400
    assert "not-in-the-spec" in response.content.decode()


@pytest.mark.parametrize("spec", BY_TYPE)
def returns_no_unsupported_refusal_for_every_parameter_and_include_the_spec_names(
    spec: SpecResource,
) -> None:
    token = token_of(role="ADMIN")
    queries = [f"{name}=x" for name in sorted(_parameters_served(spec))]
    queries += [f"_include={name}" for name in spec.includes]

    bodies = {query: get(f"/fhir/{spec.type}?{query}", token).content.decode() for query in queries}

    refused = [query for query, body in bodies.items() if "is not supported" in body]
    assert refused == []


def returns_400_when_an_include_is_not_in_the_spec() -> None:
    response = get("/fhir/Appointment?_include=Appointment:service", token_of(role="ADMIN"))

    assert response.status_code == 400


def returns_no_addition_to_the_spec_without_an_existing_adr_that_names_it() -> None:
    unnamed = [item for item in ADR_ADDITIONS if not _adr_text(item.adr, item.quote)]

    assert ADR_ADDITIONS
    assert unnamed == []


def returns_no_difference_from_the_spec_without_an_existing_adr_and_a_reason() -> None:
    differences = [item for spec in SPEC_RESOURCES for item in spec.differences]

    missing_reason = [item for item in differences if not item.reason.strip()]
    missing_adr = [item for item in differences if not _adr_text(item.adr, item.quote)]

    assert differences
    assert missing_reason == []
    assert missing_adr == []
