"""Shared helpers of the appointment action tests: sign in, build, call, read."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.models import Appointment, User
from scheduling.models.builders import STARTS_AT, Clinic, make

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

APPOINTMENTS = "/api/v1/appointments"
LOGIN = "/api/v1/auth/login"
RIGHT_PHRASE = "correct horse battery staple"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
THIRTY_MINUTES = timedelta(minutes=30)
NEXT_MONDAY = STARTS_AT + timedelta(days=7)
MONDAY_AFTER = STARTS_AT + timedelta(days=14)


def _signed_in(user: User) -> Client:
    user.password = make_password(RIGHT_PHRASE)
    user.save()
    client = Client()
    response = client.post(
        LOGIN, {"email": user.email, "password": RIGHT_PHRASE}, content_type="application/json"
    )
    assert response.status_code == 200
    return client


def _admin() -> User:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin


def _clinician_user(clinic: Clinic) -> User:
    user = clinic.clinician.user
    assert isinstance(user, User)
    user.refresh_from_db()
    return user


def _make_appointment(clinic: Clinic, **overrides: object) -> Appointment:
    starts_at = overrides.get("starts_at", STARTS_AT)
    assert isinstance(starts_at, datetime)
    fields = {
        "appointment_type": clinic.appointment_type,
        "clinician": clinic.clinician,
        "patient": clinic.patient,
        "starts_at": starts_at,
        "ends_at": starts_at + THIRTY_MINUTES,
    }
    row = make("Appointment", **{**fields, **overrides})
    assert isinstance(row, Appointment)
    return row


def _post(
    client: Client, appointment: Appointment, action: str, body: Mapping[str, object] | None = None
) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        f"{APPOINTMENTS}/{appointment.pk}/{action}", body or {}, content_type="application/json"
    )


def _cancel(
    client: Client, appointment: Appointment, reason: str = "No longer needed"
) -> _MonkeyPatchedWSGIResponse:
    return _post(client, appointment, "cancel", {"reason": reason})


def _reschedule(
    client: Client, appointment: Appointment, starts_at: datetime
) -> _MonkeyPatchedWSGIResponse:
    return _post(client, appointment, "reschedule", {"starts_at": starts_at.isoformat()})


def _status_of(appointment: Appointment) -> str:
    appointment.refresh_from_db()
    return appointment.status


def _error_code(response: _MonkeyPatchedWSGIResponse) -> str:
    return str(response.json()["error"]["code"])
