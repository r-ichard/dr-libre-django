"""Task 27a, finding #45: a text field of `/api/v1` refuses a number, as it refuses a boolean."""

import pytest
from rest_framework import serializers

from scheduling.views import auth_schemas, booking_schemas, hold_schemas, waitlist_schemas
from scheduling.views.pages import booking_forms
from scheduling.views.schemas import StrictLine, StrictSerializer, StrictText

SCHEMA_MODULES = (auth_schemas, booking_schemas, hold_schemas, waitlist_schemas, booking_forms)


def _request_schemas() -> list[type[StrictSerializer]]:
    found = {
        value
        for module in SCHEMA_MODULES
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, StrictSerializer)
        and value is not StrictSerializer
        and value.__module__ == module.__name__
    }
    return sorted(found, key=lambda schema: schema.__name__)


def _text_fields() -> list[tuple[str, str]]:
    return [
        (schema.__name__, name)
        for schema in _request_schemas()
        for name, field in schema().fields.items()
        if isinstance(field, serializers.CharField) and not field.read_only
    ]


def returns_at_least_one_text_field_when_request_schemas_are_listed() -> None:
    assert ("BookRequest", "reason") in _text_fields()


@pytest.mark.parametrize(("schema_name", "field_name"), _text_fields())
@pytest.mark.parametrize("wrong", [12345, True, 1.5, ["a"], {"a": "b"}])
def returns_refusal_when_text_field_gets_a_non_string(
    schema_name: str, field_name: str, wrong: object
) -> None:
    schema = next(item for item in _request_schemas() if item.__name__ == schema_name)
    field = schema().fields[field_name]

    with pytest.raises(serializers.ValidationError):
        field.run_validation(wrong)


@pytest.mark.parametrize(("schema_name", "field_name"), _text_fields())
def returns_refusal_when_text_field_holds_nul_byte(schema_name: str, field_name: str) -> None:
    schema = next(item for item in _request_schemas() if item.__name__ == schema_name)
    field = schema().fields[field_name]

    with pytest.raises(serializers.ValidationError):
        field.run_validation("a\x00b")


@pytest.mark.parametrize(("schema_name", "field_name"), _text_fields())
def returns_refusal_when_text_field_holds_a_control_character_django_lets_through(
    schema_name: str, field_name: str
) -> None:
    schema = next(item for item in _request_schemas() if item.__name__ == schema_name)
    field = schema().fields[field_name]

    with pytest.raises(serializers.ValidationError):
        field.run_validation("a\x01b")


def returns_refusal_when_single_line_field_holds_a_line_break() -> None:
    field = StrictLine()

    with pytest.raises(serializers.ValidationError):
        field.run_validation("a\nb")


def returns_text_when_free_text_field_holds_a_line_break() -> None:
    assert StrictText().run_validation("a\nb") == "a\nb"


@pytest.mark.parametrize("field_name", ["full_name", "email", "phone"])
def returns_refusal_when_booking_form_single_line_field_holds_a_line_break(
    field_name: str,
) -> None:
    field = booking_forms.DetailsSchema().fields[field_name]

    with pytest.raises(serializers.ValidationError):
        field.run_validation("a@example.org\n" if field_name == "email" else "a\nb")


def returns_the_rules_message_when_single_line_field_holds_a_line_break() -> None:
    with pytest.raises(serializers.ValidationError) as refused:
        StrictLine().run_validation("Saint\nAnne")

    assert [str(item) for item in refused.value.detail] == [
        'This field takes one line. Remove the line break after "Saint".'
    ]
