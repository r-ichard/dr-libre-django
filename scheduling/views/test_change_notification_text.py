"""Task 17b, #23: the notification of a cancelled or rescheduled appointment says what happened
and when, in the written date format of the pages. The text carries the time only (section 11)."""

from __future__ import annotations

import pytest

from scheduling.models import Notification
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.test_appointment_support import (
    MONDAY_AFTER,
    NEXT_MONDAY,
    NOW,
    _cancel,
    _make_appointment,
    _reschedule,
    _signed_in,
)

pytestmark = pytest.mark.django_db

PRIVATE_REASON = "private-reason-5521"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _body_of(title: str) -> str:
    return Notification.objects.get(title=title).body


def returns_text_naming_the_cancelled_time_when_appointment_is_cancelled() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)

    _cancel(_signed_in(clinic.patient), appointment, PRIVATE_REASON)

    assert _body_of("Appointment cancelled") == (
        "Your appointment on Monday 14 January 2030, 11:00 (Europe/Berlin) is cancelled."
    )


def returns_text_naming_the_new_time_when_appointment_is_rescheduled() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, starts_at=NEXT_MONDAY)

    _reschedule(_signed_in(clinic.patient), appointment, MONDAY_AFTER)

    assert _body_of("Appointment rescheduled") == (
        "Your appointment has moved to Monday 21 January 2030, 11:00 (Europe/Berlin)."
    )
