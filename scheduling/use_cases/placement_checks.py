"""Section 5.2 steps 3 and 4 and the constraint translation, split from placement for size."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg.errors
from django.db import IntegrityError
from django.db.models import Q

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.booking_rules import (
    BookingAction,
    BookingAttempt,
    BookingSummary,
    count_open_online_bookings,
    violated_rules,
)
from scheduling.domain.free_slots import SlotType, TimeRange
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, Role
from scheduling.models import Appointment, AppointmentType
from scheduling.use_cases.schedule_loading import slot_type_of

RESOURCE_BY_CONSTRAINT = {
    "appointment_no_overlap_for_clinician": "clinician",
    "appointment_no_overlap_for_patient": "patient",
    "appointment_no_overlap_for_room": "room",
}


@dataclass(frozen=True)
class PlacementSlot:
    appointment_type: AppointmentType
    window: TimeRange
    slot_type: SlotType
    zone: ZoneInfo
    now: datetime


def slot_of(appointment_type: AppointmentType, starts_at: datetime, now: datetime) -> PlacementSlot:
    slot_type = slot_type_of(appointment_type)
    return PlacementSlot(
        appointment_type,
        TimeRange(starts_at, starts_at + slot_type.duration),
        slot_type,
        ZoneInfo(appointment_type.department.hospital.time_zone),
        now,
    )


def find_conflicts(
    clinician_id: UUID, patient_id: UUID, room_id: UUID | None, window: TimeRange
) -> list[str]:
    """Resources with an active appointment overlapping the window, in the order of 5.2."""
    sharing = Q(clinician_id=clinician_id) | Q(patient_id=patient_id)
    if room_id is not None:
        sharing |= Q(room_id=room_id)
    overlapping = Appointment.objects.filter(
        sharing,
        status__in=ACTIVE_STATUSES,
        starts_at__lt=window.ends_at,
        ends_at__gt=window.starts_at,
    ).values_list("clinician_id", "patient_id", "room_id")
    rows = list(overlapping)
    return [
        resource
        for resource, taken in (
            ("clinician", any(row[0] == clinician_id for row in rows)),
            ("patient", any(row[1] == patient_id for row in rows)),
            ("room", room_id is not None and any(row[2] == room_id for row in rows)),
        )
        if taken
    ]


def busy_room_ids(room_ids: Collection[UUID], window: TimeRange) -> set[UUID]:
    taken = Appointment.objects.filter(
        room_id__in=room_ids,
        status__in=ACTIVE_STATUSES,
        starts_at__lt=window.ends_at,
        ends_at__gt=window.starts_at,
    ).values_list("room_id", flat=True)
    return {room_id for room_id in taken if room_id is not None}


def violated_booking_rules(
    actor_role: Role, patient_id: UUID, slot_is_free: bool, slot: PlacementSlot
) -> list[str]:
    attempt = BookingAttempt(
        BookingAction.BOOK,
        actor_role,
        slot.now,
        slot.window.starts_at,
        None,
        _open_online_bookings(patient_id, slot.now),
        slot.appointment_type.is_bookable_online,
        slot_is_free,
    )
    return [rule.value for rule in violated_rules(attempt)]


def _open_online_bookings(patient_id: UUID, now: datetime) -> int:
    rows = Appointment.objects.filter(patient_id=patient_id, starts_at__gt=now).values_list(
        "starts_at", "status", "source"
    )
    summaries: Sequence[BookingSummary] = [
        BookingSummary(starts_at, AppointmentStatus(status), AppointmentSource(source))
        for starts_at, status, source in rows
    ]
    return count_open_online_bookings(summaries, now)


def violated_resource(error: IntegrityError) -> str | None:
    """The resource of a no-overlap exclusion violation; None for any other integrity error."""
    cause = error.__cause__
    if not isinstance(cause, psycopg.errors.ExclusionViolation):
        return None
    return RESOURCE_BY_CONSTRAINT.get(cause.diag.constraint_name or "")
