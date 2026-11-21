"""Section 5.7: one reminder for each appointment starting within 24 hours, never twice."""

from collections.abc import Iterator
from datetime import timedelta

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, Notification
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases import reminders
from scheduling.use_cases.reminders import send_reminders
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import NOW, THIRTY_MINUTES, _admin_user

pytestmark = pytest.mark.django_db

ONE_DAY = timedelta(days=1)
REMINDER = "APPOINTMENT_REMINDER"


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-reminders", NOW)):
        yield


def _appointment(starts_in: timedelta, **overrides: object) -> Appointment:
    clinic = make_clinic()
    starts_at = NOW + starts_in
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


def _reminded_ids() -> set[object]:
    return set(Notification.objects.filter(kind=REMINDER).values_list("appointment_id", flat=True))


def returns_one_reminder_when_booked_appointment_starts_in_two_hours() -> None:
    appointment = _appointment(timedelta(hours=2))

    count = send_reminders(None)

    reminder = Notification.objects.get(kind=REMINDER)
    assert count == 1
    assert reminder.appointment_id == appointment.pk
    assert reminder.recipient_id == appointment.patient_id
    assert reminder.title == "Appointment reminder"
    assert reminder.email_pending is True


def returns_reminder_when_confirmed_appointment_starts_in_window() -> None:
    appointment = _appointment(timedelta(hours=2), status="CONFIRMED")

    send_reminders(None)

    assert _reminded_ids() == {appointment.pk}


def returns_reminder_when_appointment_starts_exactly_24_hours_ahead() -> None:
    appointment = _appointment(ONE_DAY)

    send_reminders(None)

    assert _reminded_ids() == {appointment.pk}


def returns_no_reminder_when_appointment_starts_24_hours_and_one_second_ahead() -> None:
    _appointment(ONE_DAY + timedelta(seconds=1))

    assert send_reminders(None) == 0
    assert _reminded_ids() == set()


def returns_no_reminder_when_appointment_cancelled() -> None:
    _appointment(
        timedelta(hours=2),
        status="CANCELLED",
        cancelled_at=NOW,
        cancellation_reason="No longer needed",
    )

    assert send_reminders(None) == 0


def returns_no_reminder_when_appointment_started_already() -> None:
    _appointment(-timedelta(minutes=1))

    assert send_reminders(None) == 0


@pytest.mark.parametrize("status", ["CHECKED_IN", "COMPLETED", "NO_SHOW"])
def returns_no_reminder_when_appointment_status_is_past_confirmation(status: str) -> None:
    _appointment(timedelta(hours=2), status=status)

    assert send_reminders(None) == 0


def returns_one_reminder_each_when_several_qualify() -> None:
    first = _appointment(timedelta(hours=2))
    second = _appointment(timedelta(hours=5))

    count = send_reminders(None)

    assert count == 2
    assert _reminded_ids() == {first.pk, second.pk}


def returns_nobody_reminded_twice_when_run_twice() -> None:
    _appointment(timedelta(hours=2))

    counts = [send_reminders(None), send_reminders(None)]

    assert counts == [1, 0]
    assert Notification.objects.filter(kind=REMINDER).count() == 1


def returns_audit_entry_with_count_when_reminders_created() -> None:
    _appointment(timedelta(hours=2))
    _appointment(timedelta(hours=3))
    admin = _admin_user()

    send_reminders(admin)

    audit = AuditLogEntry.objects.get(action="reminder.run")
    assert audit.metadata["counts"] == {"reminder_count": 2}
    assert audit.actor_id == admin.pk


def returns_audit_entry_without_actor_when_the_worker_runs() -> None:
    _appointment(timedelta(hours=2))

    send_reminders(None)

    assert AuditLogEntry.objects.get(action="reminder.run").actor_id is None


def returns_no_audit_entry_when_no_reminder_created() -> None:
    send_reminders(None)

    assert AuditLogEntry.objects.filter(action="reminder.run").count() == 0


def returns_one_audit_entry_when_run_twice_over_one_appointment() -> None:
    _appointment(timedelta(hours=2))

    send_reminders(None)
    send_reminders(None)

    assert AuditLogEntry.objects.filter(action="reminder.run").count() == 1


def returns_reminder_without_visit_reason_when_created() -> None:
    _appointment(timedelta(hours=2), patient_reason="planted-reminder-reason-1")

    send_reminders(None)

    reminder = Notification.objects.get(kind=REMINDER)
    assert "planted-reminder-reason-1" not in f"{reminder.title} {reminder.body}"


def returns_zero_when_a_reminder_committed_after_the_candidates_were_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment = _appointment(timedelta(hours=2))
    make(
        "Notification",
        kind=REMINDER,
        title="Appointment reminder",
        appointment=appointment,
        recipient=appointment.patient,
    )
    stale_candidates = Appointment.objects.filter(pk=appointment.pk)
    monkeypatch.setattr(reminders, "_due_appointments", lambda _now: stale_candidates)

    count = send_reminders(None)

    assert count == 0
    assert Notification.objects.filter(kind=REMINDER).count() == 1
