"""Task 09 item 8: each job is a management command that runs alone and prints its counts.
The commands read the real clock, so the rows here are built around it."""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from scheduling.models import Appointment, Notification, Session, SignInFailure, WaitlistEntry
from scheduling.models.builders import make, make_clinic

pytestmark = pytest.mark.django_db

ONE_HOUR = timedelta(hours=1)


def _run(command: str) -> list[str]:
    output = StringIO()
    call_command(command, stdout=output)
    return output.getvalue().split()


def returns_reminder_count_when_send_reminders_runs_alone() -> None:
    clinic = make_clinic()
    starts_at = datetime.now(UTC) + 2 * ONE_HOUR
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        patient=clinic.patient,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )

    assert _run("send_reminders") == ["1"]
    assert _run("send_reminders") == ["0"]
    assert Notification.objects.filter(kind="APPOINTMENT_REMINDER").count() == 1
    assert Appointment.objects.count() == 1


def returns_expired_count_when_expire_waitlist_runs_alone() -> None:
    clinic = make_clinic()
    long_ago = datetime.now(UTC) - 2 * timedelta(days=1)
    make(
        "WaitlistEntry",
        patient=clinic.patient,
        appointment_type=clinic.appointment_type,
        earliest_at=long_ago - ONE_HOUR,
        latest_at=long_ago,
    )

    assert _run("expire_waitlist") == ["1"]
    assert WaitlistEntry.objects.get().status == "EXPIRED"


def returns_both_counts_when_purge_expired_runs_alone() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=2)
    make("Session", created_at=long_ago - ONE_HOUR, expires_at=long_ago)
    make("SignInFailure", failed_at=long_ago)
    make("SignInFailure", failed_at=long_ago)

    assert _run("purge_expired") == ["1", "2"]
    assert Session.objects.count() == 0
    assert SignInFailure.objects.count() == 0


def returns_zero_when_send_pending_emails_has_nothing_to_send() -> None:
    assert _run("send_pending_emails") == ["0"]
