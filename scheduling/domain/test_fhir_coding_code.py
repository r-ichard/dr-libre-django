"""Section 15.2: a concept's first coding code, as the location kind and the department
type read it. Expected values come from FHIR R4 CodeableConcept: `coding` is a list, the
first entry is the one read, a missing or malformed part reads as no code."""

from uuid import UUID

import pytest

from scheduling.domain.fhir_common import Resource, extension
from scheduling.domain.fhir_record_write import (
    extension_value,
    first_coding_code,
    location_kind,
    reference_id,
)

ROOM_ID = UUID("22222222-2222-2222-2222-222222222222")


def returns_the_code_of_the_first_coding_when_a_concept_has_two() -> None:
    concept = {"coding": [{"code": "si"}, {"code": "ro"}]}

    assert location_kind({"physicalType": concept}) == "hospital"


def returns_the_code_when_the_concept_has_one_coding() -> None:
    assert location_kind({"physicalType": {"coding": [{"code": "ro"}]}}) == "room"


@pytest.mark.parametrize(
    "concept",
    [
        None,
        "si",
        {},
        {"coding": []},
        {"coding": "si"},
        {"coding": [{}]},
        {"coding": [{"code": 5}]},
        {"coding": [{"display": "si"}]},
    ],
)
def returns_no_kind_when_the_concept_has_no_usable_code(concept: object) -> None:
    assert location_kind({"physicalType": concept}) is None


@pytest.mark.parametrize(
    "concepts",
    [None, [], "dept", {}, [None], [{}], [{"coding": []}], [{"coding": [{"display": "dept"}]}]],
)
def returns_empty_code_when_the_first_concept_has_no_usable_code(concepts: object) -> None:
    assert first_coding_code(concepts) == ""


def returns_the_code_of_the_first_concept_when_there_are_two() -> None:
    concepts = [{"coding": [{"code": "dept"}]}, {"coding": [{"code": "other"}]}]

    assert first_coding_code(concepts) == "dept"


def returns_no_value_when_an_extension_of_another_url_holds_the_key() -> None:
    body: Resource = {"extension": [{"url": "http://example.org/other", "valueString": "x"}]}

    assert extension_value(body, "role-bio", "valueString") is None


def returns_no_value_when_the_extension_of_the_url_lacks_the_key() -> None:
    body: Resource = {"extension": [extension("role-bio", "valueInteger", 3)]}

    assert extension_value(body, "role-bio", "valueString") is None


@pytest.mark.parametrize(
    "reference",
    [None, "Room/x", {}, {"reference": 5}, {"reference": None}, {"reference": f"{ROOM_ID}"}],
)
def returns_no_id_when_a_reference_is_not_a_prefixed_text(reference: object) -> None:
    assert reference_id(reference, "Room") is None


def returns_the_id_when_a_reference_has_the_prefix() -> None:
    assert reference_id({"reference": f"Room/{ROOM_ID}"}, "Room") == ROOM_ID
