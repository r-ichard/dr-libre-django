"""Task 23, spec 15.1: a write body is checked as a FHIR resource of the URL's type and id before
any use case runs. The first element the server would not have produced is named."""

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.fhir_body import Shape, exact_elements, if_match_version

ALLOWED: Shape = {"resourceType": str, "id": str, "active": bool, "planningHorizon": {"start": str}}


def returns_none_when_every_element_is_known_and_typed() -> None:
    body = {"resourceType": "Schedule", "active": True, "planningHorizon": {"start": "2030-01-07"}}

    assert exact_elements(body, ALLOWED, "Schedule") is None


def returns_element_name_when_body_has_unknown_element() -> None:
    assert exact_elements({"resourceType": "Schedule", "comment": "x"}, ALLOWED, "Schedule") == (
        "Schedule.comment"
    )


def returns_nested_name_when_nested_element_is_unknown() -> None:
    body = {"resourceType": "Schedule", "planningHorizon": {"foo": "x"}}

    assert exact_elements(body, ALLOWED, "Schedule") == "Schedule.planningHorizon.foo"


def returns_element_name_when_element_has_wrong_type() -> None:
    body = {"resourceType": "Schedule", "active": "yes"}

    assert exact_elements(body, ALLOWED, "Schedule") == "Schedule.active"


@pytest.mark.parametrize("value", [None, [], 1, "text"])
def returns_the_type_name_when_body_is_not_an_object(value: object) -> None:
    assert exact_elements(value, ALLOWED, "Schedule") == "Schedule"


LISTED: Shape = {"name": [{"text": str}], "tags": [str]}


def returns_none_when_every_list_item_is_known_and_typed() -> None:
    assert (
        exact_elements({"name": [{"text": "a"}, {"text": "b"}], "tags": ["x"]}, LISTED, "P") is None
    )


def returns_the_list_name_when_a_list_element_is_not_a_list() -> None:
    assert exact_elements({"name": {"text": "a"}}, LISTED, "P") == "P.name"


def returns_the_list_name_when_an_item_has_the_wrong_type() -> None:
    assert exact_elements({"tags": ["x", 1]}, LISTED, "P") == "P.tags"


def returns_the_nested_name_when_an_item_of_a_list_has_an_unknown_element() -> None:
    assert exact_elements({"name": [{"text": "a"}, {"use": "x"}]}, LISTED, "P") == "P.name.use"


def returns_no_condition_when_if_match_names_version_zero() -> None:
    """Versions start at 1, so `W/"0"` is a client's placeholder for no condition."""
    assert if_match_version('W/"0"') == Success(None)
    assert if_match_version('"0"') == Success(None)
    assert if_match_version('W/"3"') == Success(3)


def returns_the_if_match_header_and_a_fixed_message_when_the_condition_is_not_a_version() -> None:
    expected = Failure.invalid_input([FieldMessage("If-Match", "Use the ETag of the record.")])

    assert if_match_version("nonsense") == expected
