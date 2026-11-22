"""Task 27a, finding #45: a text field of `/api/v1` refuses a number, as it refuses a boolean."""

from datetime import UTC, datetime

import pytest
from rest_framework import serializers

from scheduling.models.builders import STARTS_AT, make_clinic
from scheduling.views import auth_schemas, booking_schemas, clock, hold_schemas, waitlist_schemas
from scheduling.views.api_clients import browser_api_client
from scheduling.views.pages import booking_forms
from scheduling.views.schemas import StrictLine, StrictSerializer, StrictText

SECRET = "Pl4nted-Secret-9x"  # noqa: S105 - a planted test value
CONTROL_AFTER_SECRET = f"{SECRET}\x0c"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOLDS = "/api/v1/booking/holds"

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


@pytest.mark.django_db
def returns_400_without_password_when_login_password_holds_control_character() -> None:
    response = browser_api_client().post(
        "/api/v1/auth/login",
        {"email": "pat.secret@example.test", "password": CONTROL_AFTER_SECRET},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert '"Remove the character that cannot be saved."' in response.content.decode()
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def returns_400_without_token_when_link_token_holds_control_character() -> None:
    response = browser_api_client().post(
        "/api/v1/auth/link/verify",
        {"token": CONTROL_AFTER_SECRET},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert '"Remove the character that cannot be saved."' in response.content.decode()
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def returns_400_without_code_when_hold_code_holds_control_character(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    clinic = make_clinic()
    client = browser_api_client()
    hold = client.post(
        HOLDS,
        {
            "appointment_type_id": str(clinic.appointment_type.pk),
            "clinician_id": str(clinic.clinician.pk),
            "starts_at": STARTS_AT.isoformat(),
            "full_name": "Vera Visitor",
            "date_of_birth": "1985-03-14",
            "email": "vera.secret@example.test",
            "terms_accepted": True,
        },
        content_type="application/json",
    ).json()

    response = client.post(
        f"{HOLDS}/{hold['id']}/verify", {"code": "482913\x0c"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert '"Remove the character that cannot be saved."' in response.content.decode()
    assert "482913" not in response.content.decode()
