"""Section 5.6 and 4: a reschedule to the start the appointment already has changes nothing."""

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, Notification, User
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic, make_user
from scheduling.use_cases.appointment_changes import reschedule_appointment
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = STARTS_AT - timedelta(days=3)
THIRTY_MINUTES = timedelta(minutes=30)
NEXT_MONDAY = STARTS_AT + timedelta(days=7)
MONDAY_AFTER = STARTS_AT + timedelta(days=14)


@pytest.fixture(autouse=True)
def request_clock() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-reschedule-same", NOW)):
        yield


def _booked(clinic: Clinic, starts_at: datetime, status: str = "BOOKED") -> Appointment:
    row = make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        patient=clinic.patient,
        starts_at=starts_at,
        ends_at=starts_at + THIRTY_MINUTES,
        status=status,
    )
    assert isinstance(row, Appointment)
    return row


def _clinician_user(clinic: Clinic) -> User:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return user


def _admin() -> User:
    return make_user(role="ADMIN")


def returns_unchanged_appointment_and_writes_nothing_when_rescheduled_to_current_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, NEXT_MONDAY)
    room_before = appointment.room_id
    version_before = appointment.version

    result = reschedule_appointment(appointment.pk, NEXT_MONDAY, _clinician_user(clinic))

    appointment.refresh_from_db()
    assert isinstance(result, Success)
    assert appointment.starts_at == NEXT_MONDAY
    assert appointment.ends_at == NEXT_MONDAY + THIRTY_MINUTES
    assert appointment.room_id == room_before
    assert appointment.version == version_before
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 0
    assert Notification.objects.filter(kind="SCHEDULE_CHANGED").count() == 0


def returns_success_with_one_audit_entry_when_rescheduled_twice_to_the_same_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, NEXT_MONDAY)
    clinician = _clinician_user(clinic)

    first = reschedule_appointment(appointment.pk, MONDAY_AFTER, clinician)
    second = reschedule_appointment(appointment.pk, MONDAY_AFTER, clinician)

    assert isinstance(first, Success)
    assert isinstance(second, Success)
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 1


def returns_invalid_transition_and_no_audit_when_checked_in_appointment_keeps_its_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, NEXT_MONDAY, status="CHECKED_IN")

    result = reschedule_appointment(appointment.pk, NEXT_MONDAY, _admin())

    assert isinstance(result, Failure)
    assert result.code == FailureCode.INVALID_TRANSITION
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 0


def returns_forbidden_and_no_audit_when_other_patient_reschedules_to_current_start() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic, NEXT_MONDAY)
    stranger = make_user(role="PATIENT")

    to_new_start = reschedule_appointment(appointment.pk, MONDAY_AFTER, stranger)
    to_current_start = reschedule_appointment(appointment.pk, NEXT_MONDAY, stranger)

    assert isinstance(to_new_start, Failure)
    assert isinstance(to_current_start, Failure)
    assert to_current_start.code == to_new_start.code == FailureCode.FORBIDDEN
    assert AuditLogEntry.objects.filter(action="appointment.reschedule").count() == 0
