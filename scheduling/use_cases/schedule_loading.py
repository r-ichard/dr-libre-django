"""Sections 5.1 and 7.1: everything the engine needs to judge clinicians, in four queries.
Slot queries and placement both load through here, so they cannot disagree on what is free."""

from collections.abc import Collection
from datetime import datetime, timedelta
from uuid import UUID

from django.db.models import QuerySet

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.free_slots import (
    AvailabilityWindow,
    BusyInterval,
    ExistingAppointment,
    SlotType,
    TimeRange,
)
from scheduling.domain.slot_search import ClinicianSchedule
from scheduling.domain.vocabulary import AppointmentStatus, Role
from scheduling.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    BookingHold,
    ClinicianProfile,
    TimeOff,
    User,
)


def load_schedules(
    clinician_ids: Collection[UUID],
    slot_type: SlotType,
    window: TimeRange,
    now: datetime,
    ignoring_appointment_id: UUID | None = None,
    ignoring_hold_id: UUID | None = None,
) -> dict[UUID, ClinicianSchedule]:
    rules: dict[UUID, list[AvailabilityWindow]] = {key: [] for key in clinician_ids}
    time_off: dict[UUID, list[BusyInterval]] = {key: [] for key in clinician_ids}
    appointments: dict[UUID, list[ExistingAppointment]] = {key: [] for key in clinician_ids}
    for rule in AvailabilityRule.objects.filter(clinician_id__in=clinician_ids):
        rules[rule.clinician_id].append(_window_of(rule))
    overlapping_off = TimeOff.objects.filter(
        clinician_id__in=clinician_ids, starts_at__lt=window.ends_at, ends_at__gt=window.starts_at
    )
    for off in overlapping_off:
        time_off[off.clinician_id].append(BusyInterval(off.starts_at, off.ends_at))
    # Existing ends are extended by the buffer, so anything ending within it still blocks.
    earliest_end = window.starts_at - slot_type.buffer
    booked_rows = Appointment.objects.filter(
        status__in=ACTIVE_STATUSES,
        clinician_id__in=clinician_ids,
        starts_at__lt=window.ends_at,
        ends_at__gt=earliest_end,
    )
    if ignoring_appointment_id is not None:
        booked_rows = booked_rows.exclude(pk=ignoring_appointment_id)
    for booked in booked_rows:
        appointments[booked.clinician_id].append(
            ExistingAppointment(booked.starts_at, booked.ends_at, AppointmentStatus(booked.status))
        )
    holds = BookingHold.objects.filter(
        clinician_id__in=clinician_ids,
        expires_at__gt=now,
        starts_at__lt=window.ends_at,
        ends_at__gt=earliest_end,
    )
    if ignoring_hold_id is not None:
        holds = holds.exclude(pk=ignoring_hold_id)
    for hold in holds:
        appointments[hold.clinician_id].append(
            ExistingAppointment(hold.starts_at, hold.ends_at, AppointmentStatus.BOOKED)
        )
    return {
        key: ClinicianSchedule(rules[key], time_off[key], appointments[key])
        for key in clinician_ids
    }


def _window_of(rule: AvailabilityRule) -> AvailabilityWindow:
    return AvailabilityWindow(
        rule.weekday,
        rule.start_time,
        rule.end_time,
        timedelta(minutes=rule.slot_step_minutes),
        rule.valid_from,
        rule.valid_to,
    )


def online_only_for(user: User | None) -> bool:
    """Section 6.1: visitors and patients see what the public search shows; staff see all."""
    return user is None or Role(user.role) == Role.PATIENT


def active_appointment_type(appointment_type_id: UUID, online_only: bool) -> AppointmentType | None:
    types = AppointmentType.objects.select_related("department__hospital").filter(
        pk=appointment_type_id, is_active=True
    )
    return (types.filter(is_bookable_online=True) if online_only else types).first()


def slot_type_of(appointment_type: AppointmentType) -> SlotType:
    return SlotType(
        timedelta(minutes=appointment_type.duration_minutes),
        timedelta(minutes=appointment_type.buffer_minutes),
    )


def department_clinicians(
    appointment_type: AppointmentType, clinician_id: UUID | None, online_only: bool
) -> QuerySet[ClinicianProfile]:
    """Active clinicians of the type's department, narrowed to one when named; online callers do
    not get the ones the public search hides."""
    clinicians = ClinicianProfile.objects.filter(
        department_id=appointment_type.department_id, user__is_active=True
    )
    if online_only:
        clinicians = clinicians.filter(
            specialty__is_active=True, department__hospital__is_active=True
        )
    return clinicians if clinician_id is None else clinicians.filter(pk=clinician_id)
