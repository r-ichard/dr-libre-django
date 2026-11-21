"""Uniqueness the database enforces: codes, email, one profile per user, hashes, reminders."""

import pytest

from scheduling.models.builders import field_of, make, model_class, refuses, unique_hash

pytestmark = pytest.mark.django_db

CODED_MODELS = ["Hospital", "Department", "Specialty", "Room", "AppointmentType"]


@pytest.mark.parametrize("model_name", CODED_MODELS)
def rejects_row_when_code_repeats(model_name: str) -> None:
    first = make(model_name, code="shared-code")

    refuses(model_name, code="shared-code")

    assert model_class(model_name)._default_manager.filter(code="shared-code").count() == 1
    assert field_of(first, "code") == "shared-code"


@pytest.mark.parametrize("model_name", CODED_MODELS)
def returns_both_rows_when_codes_differ(model_name: str) -> None:
    make(model_name, code="first-code")

    make(model_name, code="second-code")

    assert model_class(model_name)._default_manager.count() == 2


def rejects_second_user_when_email_repeats() -> None:
    make("User", email="same@example.com")

    refuses("User", email="same@example.com")


def returns_both_users_when_emails_differ() -> None:
    make("User", email="one@example.com")

    make("User", email="two@example.com")

    assert model_class("User")._default_manager.count() == 2


def rejects_second_profile_when_user_already_has_one() -> None:
    profile = make("ClinicianProfile")

    refuses("ClinicianProfile", user=field_of(profile, "user"))


def returns_second_profile_when_user_differs() -> None:
    make("ClinicianProfile")

    make("ClinicianProfile")

    assert model_class("ClinicianProfile")._default_manager.count() == 2


@pytest.mark.parametrize(
    ("model_name", "hash_field"), [("Session", "token_hash"), ("SignInLink", "token_hash")]
)
def rejects_row_when_hash_repeats(model_name: str, hash_field: str) -> None:
    make(model_name, **{hash_field: "b" * 64})

    refuses(model_name, **{hash_field: "b" * 64})


@pytest.mark.parametrize(
    ("model_name", "hash_field"), [("Session", "token_hash"), ("SignInLink", "token_hash")]
)
def returns_both_rows_when_hashes_differ(model_name: str, hash_field: str) -> None:
    make(model_name, **{hash_field: unique_hash()})

    make(model_name, **{hash_field: unique_hash()})

    assert model_class(model_name)._default_manager.count() == 2


def rejects_second_reminder_when_appointment_already_has_one() -> None:
    appointment = make("Appointment")
    make("Notification", kind="APPOINTMENT_REMINDER", appointment=appointment)

    refuses("Notification", kind="APPOINTMENT_REMINDER", appointment=appointment)


def returns_second_notification_when_kind_is_not_a_reminder() -> None:
    appointment = make("Appointment")
    make("Notification", kind="APPOINTMENT_REMINDER", appointment=appointment)

    make("Notification", kind="SCHEDULE_CHANGED", appointment=appointment)

    assert model_class("Notification")._default_manager.filter(appointment=appointment).count() == 2
