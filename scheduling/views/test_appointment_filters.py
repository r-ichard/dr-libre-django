"""Section 14 GET /appointments: each filter narrows, range ends are half open, order by start."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.models import Appointment, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.views import clock

pytestmark = pytest.mark.django_db

APPOINTMENTS = "/api/v1/appointments"
RIGHT_PHRASE = "correct horse battery staple"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
THIRTY_MINUTES = timedelta(minutes=30)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _admin_client() -> Client:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    admin.password = make_password(RIGHT_PHRASE)
    admin.save()
    client = Client()
    login = client.post(
        "/api/v1/auth/login",
        {"email": admin.email, "password": RIGHT_PHRASE},
        content_type="application/json",
    )
    assert login.status_code == 200
    return client


def _appointment(
    clinic: Clinic, starts_at: datetime = STARTS_AT, **overrides: object
) -> Appointment:
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


def _ids(client: Client, query: str) -> list[str]:
    response = client.get(f"{APPOINTMENTS}?{query}")
    assert response.status_code == 200
    return [item["id"] for item in response.json()["results"]]


def returns_only_that_patient_when_admin_filters_by_patient() -> None:
    clinic = make_clinic()
    wanted = _appointment(clinic)
    _appointment(clinic, STARTS_AT + timedelta(days=1), patient=make("User"))

    assert _ids(_admin_client(), f"patient_id={clinic.patient.pk}") == [str(wanted.pk)]


def returns_only_that_clinician_when_admin_filters_by_clinician() -> None:
    clinic = make_clinic()
    wanted = _appointment(clinic)
    other = add_clinician(clinic.department)
    _appointment(clinic, STARTS_AT + timedelta(days=1), clinician=other)

    assert _ids(_admin_client(), f"clinician_id={clinic.clinician.pk}") == [str(wanted.pk)]


def returns_start_in_and_end_out_when_range_ends_touch_appointments() -> None:
    clinic = make_clinic()
    at_from = _appointment(clinic, datetime(2030, 1, 10, 0, 0, tzinfo=UTC))
    _appointment(clinic, datetime(2030, 1, 11, 0, 0, tzinfo=UTC))

    found = _ids(_admin_client(), "from=2030-01-10T00:00:00Z&to=2030-01-11T00:00:00Z")

    assert found == [str(at_from.pk)]


def returns_earliest_start_first_when_listing() -> None:
    clinic = make_clinic()
    later = _appointment(clinic, STARTS_AT + timedelta(days=1))
    earlier = _appointment(clinic, STARTS_AT)

    assert _ids(_admin_client(), "") == [str(earlier.pk), str(later.pk)]


@pytest.mark.parametrize(
    "window",
    [
        "from=2030-01-10T00:00:00Z&to=2030-01-10T00:00:00Z",
        "from=2030-01-11T00:00:00Z&to=2030-01-10T00:00:00Z",
    ],
)
def returns_400_invalid_input_naming_to_when_to_is_not_after_from(window: str) -> None:
    response = _admin_client().get(f"{APPOINTMENTS}?{window}")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert [item["field"] for item in error["details"]["fields"]] == ["to"]


@pytest.mark.parametrize("window", ["from=2030-01-10T00:00:00Z", "to=2030-01-10T00:00:00Z"])
def returns_200_when_only_one_end_of_the_range_is_given(window: str) -> None:
    response = _admin_client().get(f"{APPOINTMENTS}?{window}")

    assert response.status_code == 200
