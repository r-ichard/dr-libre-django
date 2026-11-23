"""Section 8: the portal's "Done" notice comes from what the server just did, shown once,
and never from a value in the address."""

from __future__ import annotations

from datetime import timedelta

import pytest

from scheduling.models.builders import STARTS_AT, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, PHRASE, signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

LIST_PATH = "/patient/appointments"
PROFILE_PATH = "/patient/profile"
CANCELLED_TEXT = "Your appointment is cancelled."


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.mark.parametrize("key", ["cancelled", "rescheduled", "saved", "password-changed"])
def returns_no_notice_when_address_carries_a_notice_value(key: str) -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    html = client.get(f"{LIST_PATH}?notice={key}").content.decode()
    profile_html = client.get(f"{PROFILE_PATH}?notice={key}").content.decode()

    assert "Done." not in html
    assert "Done." not in profile_html


def returns_cancelled_notice_once_after_cancelling() -> None:
    clinic = make_clinic()
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT + timedelta(days=7),
        ends_at=STARTS_AT + timedelta(days=7, minutes=30),
    )
    client = signed_in_patient(clinic.patient)

    answer = browser_post(client, f"{LIST_PATH}/{appointment.pk}/cancel", {"reason": "Cannot come"})
    first = client.get(answer["Location"]).content.decode()
    second = client.get(answer["Location"]).content.decode()

    assert answer.status_code == 303
    cookie = answer.cookies["drlibre_notice"]
    assert (cookie["max-age"], cookie["httponly"], cookie["samesite"]) == (60, True, "Strict")
    assert "notice" not in answer["Location"]
    assert CANCELLED_TEXT in first
    assert CANCELLED_TEXT not in second


def returns_password_changed_notice_once_after_changing_the_password() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    answer = browser_post(
        client,
        "/patient/profile/password",
        {"current_password": PHRASE, "new_password": "a-brand-new-password"},
    )
    first = client.get(answer["Location"]).content.decode()
    second = client.get(answer["Location"]).content.decode()

    assert answer.status_code == 303
    assert "notice" not in answer["Location"]
    assert "Done." in first
    assert "Done." not in second
