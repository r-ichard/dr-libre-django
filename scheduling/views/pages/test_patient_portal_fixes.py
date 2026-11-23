"""Section 8: patient portal pages as the server renders them."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scheduling.models.builders import STARTS_AT, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient

pytestmark = pytest.mark.django_db

LIST_PATH = "/patient/appointments"
STYLESHEET = Path(__file__).resolve().parents[3] / "static" / "css" / "components.css"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _list_html(status: str, starts_at: datetime) -> str:
    clinic = make_clinic()
    cancelled = (
        {"cancelled_at": NOW, "cancellation_reason": "Cancelled"} if status == "CANCELLED" else {}
    )
    make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
        **cancelled,
    )
    return signed_in_patient(clinic.patient).get(LIST_PATH).content.decode()


@pytest.mark.parametrize("status", ["COMPLETED", "NO_SHOW", "CANCELLED"])
def returns_no_call_hint_when_a_past_appointment_is_finished(status: str) -> None:
    html = _list_html(status, NOW - timedelta(days=3))

    assert "Call " not in html and "already took place" not in html


def returns_call_hint_when_a_booked_appointment_is_less_than_24_hours_ahead() -> None:
    html = _list_html("BOOKED", NOW + timedelta(hours=5))

    assert "starts in less than 24 hours" in html and "Call " in html


def returns_call_hint_when_a_booked_appointment_has_started() -> None:
    html = _list_html("BOOKED", NOW - timedelta(minutes=10))

    assert "already started" in html and "Call " in html


def returns_card_list_around_appointment_cards() -> None:
    html = _list_html("BOOKED", STARTS_AT + timedelta(days=7))

    assert '<ul class="card-list"' in html


def returns_spacing_token_gap_in_card_list_style() -> None:
    rule = STYLESHEET.read_text().split(".card-list", 1)[1].split("}", 1)[0]

    assert "gap: var(--space-4)" in rule
