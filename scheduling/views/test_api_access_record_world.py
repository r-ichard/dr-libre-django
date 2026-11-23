"""The records the record walk names: appointments, freed slots, waitlist entries and inactive
catalog records, for the world's patients and clinicians. Mondays come from one counter, so no two
records share a time."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import count

from django.db.models import Model

from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, WaitlistStatus
from scheduling.models import (
    Appointment,
    ClinicianProfile,
    Hospital,
    Specialty,
    User,
    WaitlistEntry,
)
from scheduling.models.builders import add_clinician, make
from scheduling.views import clock
from scheduling.views.test_api_access_rows import Caller
from scheduling.views.test_api_access_world import World

# A week after the frozen NOW, so the patient's 24-hour cancellation window is open.
FIRST_MONDAY = date(2030, 1, 14)
BOOKING_TIME = time(10, 0, tzinfo=UTC)
SLOT = timedelta(minutes=30)
FREED_REASON = "Clinician unavailable"


@dataclass(frozen=True)
class RecordWorld:
    second_clinician: ClinicianProfile
    inactive_hospital: Hospital
    inactive_specialty: Specialty
    inactive_provider: ClinicianProfile
    mondays: Iterator[date]


def _made[Row: Model](model_name: str, kind: type[Row], **overrides: object) -> Row:
    row = make(model_name, **overrides)
    if not isinstance(row, kind):
        raise TypeError(f"expected {kind.__name__}")
    return row


def _mondays() -> Iterator[date]:
    return (FIRST_MONDAY + timedelta(weeks=week) for week in count())


def _build_record_world(world: World) -> RecordWorld:
    department = world.appointment_type.department
    second_user = _made("User", User, role="CLINICIAN")
    inactive_user = _made("User", User, role="CLINICIAN", is_active=False)
    return RecordWorld(
        second_clinician=add_clinician(department, user=second_user),
        inactive_hospital=_made("Hospital", Hospital, is_active=False),
        inactive_specialty=_made("Specialty", Specialty, is_active=False),
        inactive_provider=add_clinician(department, user=inactive_user),
        mondays=_mondays(),
    )


def _appointment(
    world: World,
    record_world: RecordWorld,
    patient: User,
    clinician: ClinicianProfile,
    status: AppointmentStatus,
    freed: bool = False,
) -> Appointment:
    starts_at = datetime.combine(next(record_world.mondays), BOOKING_TIME)
    return _made(
        "Appointment",
        Appointment,
        patient=patient,
        clinician=clinician,
        appointment_type=world.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + SLOT,
        status=status,
        # Staff-made, so the patient's open online bookings limit (§5.3) does not refuse the accept.
        source=AppointmentSource.STAFF,
        cancelled_at=clock.now_utc() if freed else None,
        cancellation_reason=FREED_REASON if freed else "",
    )


def _appointment_pair(
    record_world: RecordWorld, world: World, status: AppointmentStatus
) -> tuple[Appointment, Appointment]:
    """The first is the world's patient with its clinician, the second another patient's."""
    own = _appointment(world, record_world, world.users[Caller.PATIENT], world.clinician, status)
    other = _appointment(
        world, record_world, world.passwordless_patient, record_world.second_clinician, status
    )
    return own, other


def _entry(
    world: World, record_world: RecordWorld, patient: User, status: WaitlistStatus
) -> WaitlistEntry:
    """Each entry has a freed slot of its own, which its window admits and no other does."""
    freed = _appointment(
        world,
        record_world,
        world.passwordless_patient,
        world.clinician,
        AppointmentStatus.CANCELLED,
        freed=True,
    )
    offered = freed if status == WaitlistStatus.OFFERED else None
    return _made(
        "WaitlistEntry",
        WaitlistEntry,
        patient=patient,
        appointment_type=world.appointment_type,
        earliest_at=freed.starts_at,
        latest_at=freed.ends_at,
        status=status,
        offered_appointment=offered,
    )


def _waitlist_pair(
    record_world: RecordWorld, world: World, status: WaitlistStatus
) -> tuple[WaitlistEntry, WaitlistEntry]:
    own = _entry(world, record_world, world.users[Caller.PATIENT], status)
    other = _entry(world, record_world, world.passwordless_patient, status)
    return own, other
