"""Section 5.8 step 2: cancelling an appointment offers the freed slot in the same transaction."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import timedelta

import pytest
from django.core import mail

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, Notification, WaitlistEntry
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.use_cases import waitlist
from scheduling.use_cases.appointment_changes import cancel_appointment
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import (
    FOREIGN_REASON,
    NOW,
    ONE_DAY,
    SLOT,
    _admin_user,
    _booked_slot,
    _entry_aged,
    _entry_for,
)

pytestmark = pytest.mark.django_db

OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-cancel-offer", NOW)):
        yield


def _cancel(appointment: Appointment) -> None:
    result = cancel_appointment(appointment.pk, "no longer needed", _admin_user())
    assert isinstance(result, Success), result


def _status_of(entry: WaitlistEntry) -> str:
    entry.refresh_from_db()
    return entry.status


def returns_offered_and_linked_when_cancel_frees_a_matching_slot() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic)

    _cancel(freed)

    entry.refresh_from_db()
    assert entry.status == "OFFERED"
    assert entry.offered_appointment_id == freed.pk


def returns_oldest_entry_offered_when_two_wait_and_others_stay_waiting() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    newer = _entry_aged(clinic, timedelta(hours=1))
    oldest = _entry_aged(clinic, timedelta(hours=9))

    _cancel(freed)

    assert _status_of(oldest) == "OFFERED"
    assert _status_of(newer) == "WAITING"


def returns_waiting_when_entry_prefers_another_clinician() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic, preferred_clinician=other)

    _cancel(freed)

    assert _status_of(entry) == "WAITING"


def returns_offered_when_entry_prefers_the_freed_clinician() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic, preferred_clinician=clinic.clinician)

    _cancel(freed)

    assert _status_of(entry) == "OFFERED"


def returns_waiting_when_window_does_not_contain_the_freed_slot() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic, earliest_at=SLOT + timedelta(hours=1), latest_at=SLOT + ONE_DAY)

    _cancel(freed)

    assert _status_of(entry) == "WAITING"


def returns_waiting_when_entry_is_for_another_type() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    other_type = make("AppointmentType", department=clinic.department)
    entry = _entry_for(clinic, appointment_type=other_type)

    _cancel(freed)

    assert _status_of(entry) == "WAITING"


def returns_unchanged_cancel_when_no_entry_matches() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)

    _cancel(freed)

    freed.refresh_from_db()
    assert freed.status == "CANCELLED"
    assert AuditLogEntry.objects.filter(action="waitlist.offer").count() == 0
    assert Notification.objects.filter(kind="WAITLIST_OFFERED").count() == 0


def returns_both_audit_entries_when_cancel_offers_a_slot() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    _entry_for(clinic)

    _cancel(freed)

    actions = sorted(AuditLogEntry.objects.values_list("action", flat=True))
    assert actions == ["appointment.cancel", "waitlist.offer"]


def returns_offer_email_without_foreign_reason_when_cancel_offers_a_slot(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic)

    with django_capture_on_commit_callbacks(execute=True):
        _cancel(freed)

    offer_notification = Notification.objects.get(kind="WAITLIST_OFFERED")
    assert offer_notification.waitlist_entry_id == entry.pk
    assert offer_notification.appointment_id is None
    to_patient = [message for message in mail.outbox if message.to == [clinic.patient.email]]
    assert len(to_patient) == 1
    assert "11:00" in to_patient[0].body
    assert FOREIGN_REASON not in f"{to_patient[0].body} {to_patient[0].subject}"


def returns_cancel_rolled_back_when_offering_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic)

    def failing_notify(*_arguments: object) -> None:
        raise RuntimeError("notification down")

    monkeypatch.setattr(waitlist, "notify_waitlist_offer", failing_notify)

    with pytest.raises(RuntimeError, match="notification down"):
        _cancel(freed)

    freed.refresh_from_db()
    assert freed.status == "BOOKED"
    assert _status_of(entry) == "WAITING"
    assert AuditLogEntry.objects.filter(action="appointment.cancel").count() == 0


def returns_failure_unchanged_when_cancelling_an_already_cancelled_appointment() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    _entry_for(clinic)
    _cancel(freed)

    again = cancel_appointment(freed.pk, "twice", _admin_user())

    assert again == Failure.invalid_transition("CANCELLED")
    assert WaitlistEntry.objects.filter(status="OFFERED").count() == 1


def returns_waiting_when_entry_window_starts_after_slot_by_one_second() -> None:
    clinic = make_clinic()
    freed = _booked_slot(clinic)
    entry = _entry_for(clinic, earliest_at=SLOT + timedelta(seconds=1))

    _cancel(freed)

    assert _status_of(entry) == "WAITING"
