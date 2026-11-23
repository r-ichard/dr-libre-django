"""Task 27a, finding #41: the list shows the last day chosen, not the day after it."""

from datetime import UTC, datetime

import pytest

from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views.pages.booking_pages_support import signed_in_patient

pytestmark = pytest.mark.django_db


def _listed_html(earliest_at: datetime, latest_at: datetime) -> str:
    hospital = make("Hospital", time_zone="Europe/Berlin")
    appointment_type = make("AppointmentType", department=make("Department", hospital=hospital))
    patient = make("User")
    assert isinstance(patient, User)
    make(
        "WaitlistEntry",
        patient=patient,
        appointment_type=appointment_type,
        earliest_at=earliest_at,
        latest_at=latest_at,
    )
    return signed_in_patient(patient).get("/patient/waitlist").content.decode()


def returns_chosen_last_day_when_window_of_two_days_is_listed() -> None:
    html = _listed_html(
        datetime(2026, 11, 25, 23, 0, tzinfo=UTC), datetime(2026, 11, 27, 23, 0, tzinfo=UTC)
    )

    assert "Thursday 26 November 2026 to Friday 27 November 2026 (Europe/Berlin)" in html


def returns_wanted_label_when_window_covers_several_days() -> None:
    html = _listed_html(
        datetime(2026, 11, 22, 23, 0, tzinfo=UTC), datetime(2026, 11, 29, 23, 0, tzinfo=UTC)
    )

    assert (
        "<dt>Wanted</dt><dd>from Monday 23 November 2026 to Sunday 29 November 2026 "
        "(Europe/Berlin)</dd>"
    ) in html
    assert "Wanted between" not in html


def returns_wanted_label_when_window_covers_one_day() -> None:
    html = _listed_html(
        datetime(2026, 11, 25, 23, 0, tzinfo=UTC), datetime(2026, 11, 26, 23, 0, tzinfo=UTC)
    )

    assert "<dt>Wanted</dt><dd>Thursday 26 November 2026 (Europe/Berlin)</dd>" in html
    assert "Wanted between" not in html
