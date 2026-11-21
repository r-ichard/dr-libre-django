"""Section 5.7: two runs at the same time remind once. Rows are committed from two threads, so the
test transaction cannot hold them."""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection

from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, Notification
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.reminders import send_reminders
from scheduling.use_cases.request_context import bind_request_context

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("committed_rows")]

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


def _appointment_in_two_hours() -> None:
    clinic = make_clinic()
    starts_at = NOW + timedelta(hours=2)
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        patient=clinic.patient,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )


def returns_one_reminder_when_two_runs_overlap() -> None:
    _appointment_in_two_hours()
    barrier = threading.Barrier(2)
    counts: list[int] = []

    def run() -> None:
        try:
            with bind_request_context(RequestContext("corr-overlap", NOW)):
                barrier.wait(timeout=10)
                counts.append(send_reminders(None))
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(counts) == [0, 1]
    assert Notification.objects.filter(kind="APPOINTMENT_REMINDER").count() == 1
    assert AuditLogEntry.objects.filter(action="reminder.run").count() == 1
