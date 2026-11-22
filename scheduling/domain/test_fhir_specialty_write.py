from uuid import uuid4

import pytest

from scheduling.domain.fhir_specialty import INACTIVE_DECLARATION
from scheduling.domain.fhir_specialty_write import (
    BUILT_ELEMENTS,
    Concept,
    StoredConcept,
    desired_concepts,
    plan_changes,
)

INACTIVE = {"code": "inactive", "valueBoolean": True}


def _body(*concepts: dict[str, object]) -> dict[str, object]:
    return {"resourceType": "CodeSystem", "concept": list(concepts)}


def returns_concepts_in_body_order_when_body_is_valid() -> None:
    body = _body(
        {"code": "cardio", "display": "Cardiology"},
        {"code": "Derm.1_x-y", "display": "Skin", "property": [INACTIVE]},
        {"code": "neuro", "display": "Neuro", "property": [{**INACTIVE, "valueBoolean": False}]},
    )

    assert desired_concepts(body) == (
        Concept(0, "cardio", "Cardiology", False),
        Concept(1, "Derm.1_x-y", "Skin", True),
        Concept(2, "neuro", "Neuro", False),
    )


def returns_no_concepts_when_body_lists_none() -> None:
    assert desired_concepts({"count": 0}) == ()


def returns_the_built_element_name_when_a_built_element_differs() -> None:
    assert desired_concepts({"url": "x"}) == "CodeSystem.url"
    assert desired_concepts({"property": []}) == "CodeSystem.property"
    assert desired_concepts({"caseSensitive": True}) == "CodeSystem.caseSensitive"


def returns_no_error_when_built_elements_have_the_server_values() -> None:
    assert BUILT_ELEMENTS["property"] == [INACTIVE_DECLARATION]
    assert desired_concepts({**BUILT_ELEMENTS, "concept": []}) == ()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"concept": "x"}, "CodeSystem.concept"),
        ({"concept": [], "count": 1}, "CodeSystem.count"),
        ({"concept": ["x"]}, "CodeSystem.concept[0]"),
        ({"concept": [{"display": "A"}]}, "CodeSystem.concept[0].code"),
        ({"concept": [{"code": 5, "display": "A"}]}, "CodeSystem.concept[0].code"),
        ({"concept": [{"code": "a b", "display": "A"}]}, "CodeSystem.concept[0].code"),
        ({"concept": [{"code": "a" * 51, "display": "A"}]}, "CodeSystem.concept[0].code"),
        ({"concept": [{"code": "a", "display": " "}]}, "CodeSystem.concept[0].display"),
        ({"concept": [{"code": "a"}]}, "CodeSystem.concept[0].display"),
        ({"concept": [{"code": "a", "display": 1}]}, "CodeSystem.concept[0].display"),
        (
            {"concept": [{"code": "a", "display": "A"}, {"code": "A", "display": "B"}]},
            "CodeSystem.concept[1].code",
        ),
        (
            {"concept": [{"code": "a", "display": "A", "property": {}}]},
            "CodeSystem.concept[0].property",
        ),
        (
            {"concept": [{"code": "a", "display": "A", "property": [INACTIVE, INACTIVE]}]},
            "CodeSystem.concept[0].property",
        ),
        (
            {"concept": [{"code": "a", "display": "A", "property": ["x"]}]},
            "CodeSystem.concept[0].property",
        ),
        (
            {
                "concept": [
                    {
                        "code": "a",
                        "display": "A",
                        "property": [{"code": "other", "valueBoolean": True}],
                    }
                ]
            },
            "CodeSystem.concept[0].property",
        ),
        (
            {
                "concept": [
                    {
                        "code": "a",
                        "display": "A",
                        "property": [{"code": "inactive", "valueBoolean": "yes"}],
                    }
                ]
            },
            "CodeSystem.concept[0].property",
        ),
        (
            {"concept": [{"code": "a", "display": "A", "property": [{**INACTIVE, "extra": 1}]}]},
            "CodeSystem.concept[0].property",
        ),
    ],
)
def returns_the_element_name_when_the_body_is_invalid(
    body: dict[str, object], expected: str
) -> None:
    assert desired_concepts(body) == expected


def _stored(code: str, name: str, is_active: bool = True) -> StoredConcept:
    return StoredConcept(uuid4(), code, name, is_active)


def returns_removals_then_edits_then_adds_when_changes_planned() -> None:
    gone, renamed, same = _stored("a", "A"), _stored("b", "B"), _stored("c", "C")
    desired = (
        Concept(0, "new", "New", False),
        Concept(1, "B", "Bee", False),
        Concept(2, "c", "C", False),
    )

    removals, edits, adds = plan_changes((gone, renamed, same), desired)

    assert [(c.stored, c.concept) for c in removals] == [(gone, None)]
    assert [(c.stored, c.concept) for c in edits] == [(renamed, desired[1])]
    assert [(c.stored, c.concept) for c in adds] == [(None, desired[0])]


def returns_an_edit_when_only_the_active_state_differs() -> None:
    active, inactive = _stored("a", "A"), _stored("b", "B", False)
    desired = (Concept(0, "a", "A", True), Concept(1, "b", "B", False))

    _, edits, _ = plan_changes((active, inactive), desired)

    assert [c.stored for c in edits] == [active, inactive]


def returns_no_changes_when_name_is_equal_after_trim_and_state_is_equal() -> None:
    row = _stored("a", "A")

    assert plan_changes((row,), (Concept(0, "A", " A ", False),)) == ((), (), ())


def returns_a_removal_for_every_row_when_desired_is_empty() -> None:
    rows = (_stored("a", "A"), _stored("b", "B"))

    removals, edits, adds = plan_changes(rows, ())

    assert ([c.stored for c in removals], edits, adds) == (list(rows), (), ())
