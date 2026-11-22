"""Task 27a, finding #41: the list shows the last day chosen, not the day after it."""

from datetime import UTC, datetime

import pytest

from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views.pages.booking_pages_support import signed_in_patient

pytestmark = pytest.mark.django_db


def returns_chosen_last_day_when_window_of_two_days_is_listed() -> None:
    hospital = make("Hospital", time_zone="Europe/Berlin")
    appointment_type = make("AppointmentType", department=make("Department", hospital=hospital))
    patient = make("User")
    assert isinstance(patient, User)
    make(
        "WaitlistEntry",
        patient=patient,
        appointment_type=appointment_type,
        earliest_at=datetime(2026, 11, 25, 23, 0, tzinfo=UTC),
        latest_at=datetime(2026, 11, 27, 23, 0, tzinfo=UTC),
    )

    html = signed_in_patient(patient).get("/patient/waitlist").content.decode()

    assert "Thursday 26 November 2026 to Friday 27 November 2026 (Europe/Berlin)" in html
