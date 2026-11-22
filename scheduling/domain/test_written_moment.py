"""Task 25b: one way to write a moment for a person, the zone always named."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.email_content import EmailSubject, patient_email
from scheduling.domain.placement_rules import booked_notification_text
from scheduling.domain.written_moment import written_moment

BERLIN = ZoneInfo("Europe/Berlin")
WRITTEN = "Monday 23 November 2026, 13:00 (Europe/Berlin)"


def returns_monday_23_november_2026_1300_europe_berlin_when_utc_is_12_00() -> None:
    assert written_moment(datetime(2026, 11, 23, 12, 0, tzinfo=UTC), BERLIN) == WRITTEN


def returns_the_next_local_day_when_sydney_is_past_midnight() -> None:
    moment = datetime(2026, 11, 23, 14, 30, tzinfo=UTC)

    assert (
        written_moment(moment, ZoneInfo("Australia/Sydney"))
        == "Tuesday 24 November 2026, 01:30 (Australia/Sydney)"
    )


def returns_day_without_leading_zero_when_day_is_below_ten() -> None:
    moment = datetime(2026, 3, 2, 8, 5, tzinfo=UTC)

    assert written_moment(moment, ZoneInfo("UTC")) == "Monday 2 March 2026, 08:05 (UTC)"


def returns_the_written_moment_in_the_booked_notification() -> None:
    moment = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

    assert booked_notification_text(moment, BERLIN) == f"Your appointment is on {WRITTEN}."


def returns_the_written_moment_on_the_when_line_of_the_patient_email() -> None:
    subject = EmailSubject(
        "Appointment booked",
        "http://x.test/sign-in",
        starts_at=datetime(2026, 11, 23, 12, 0, tzinfo=UTC),
        time_zone=BERLIN,
    )

    assert f"When: {WRITTEN}\n" in patient_email(subject).body
