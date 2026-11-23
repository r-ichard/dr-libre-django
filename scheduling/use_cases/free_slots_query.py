"""Section 5.1 and 14 GET /slots: the free slots of one clinician or of a whole department."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import FilteredRelation, Q

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.booking_rules import earliest_offered_start
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.free_slots import SlotType, TimeRange
from scheduling.domain.slot_search import (
    MAXIMUM_QUERY_DAYS,
    QueryTooWide,
    SlotOffer,
    free_slots_by_start,
    starts_with_free_room,
)
from scheduling.models import AppointmentType, Room
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import (
    active_appointment_type,
    department_clinicians,
    load_schedules,
    slot_type_of,
)

RoomRow = tuple[UUID, TimeRange | None]


@dataclass(frozen=True)
class FoundSlots:
    offers: list[SlotOffer]
    duration: timedelta
    time_zone: str


def find_free_slots(
    appointment_type_id: UUID, clinician_id: UUID | None, window: TimeRange, online_only: bool
) -> Result[FoundSlots]:
    if window.ends_at - window.starts_at > timedelta(days=MAXIMUM_QUERY_DAYS):
        return _too_wide()
    appointment_type = active_appointment_type(appointment_type_id, online_only)
    if appointment_type is None:
        return Failure.not_found()
    slot_type = slot_type_of(appointment_type)
    time_zone_name = appointment_type.department.hospital.time_zone
    room_rows: list[RoomRow] = []
    if appointment_type.needs_room:
        room_rows = _room_rows(appointment_type, window, slot_type.duration)
        if not room_rows:
            return Success(FoundSlots([], slot_type.duration, time_zone_name))
    clinicians = department_clinicians(appointment_type, clinician_id, online_only)
    clinician_ids = list(clinicians.values_list("pk", flat=True))
    if clinician_id is not None and not clinician_ids:
        return Failure.not_found()
    now = current_request_context().now
    schedules = load_schedules(clinician_ids, slot_type, window, now)
    earliest_start = earliest_offered_start(now, online_only)
    offers = free_slots_by_start(
        schedules, slot_type, window, earliest_start, ZoneInfo(time_zone_name)
    )
    if isinstance(offers, QueryTooWide):
        return _too_wide()
    if appointment_type.needs_room:
        offers = _with_free_room(offers, slot_type, room_rows)
    return Success(FoundSlots(offers, slot_type.duration, time_zone_name))


def _room_rows(
    appointment_type: AppointmentType, window: TimeRange, duration: timedelta
) -> list[RoomRow]:
    """One row per active room of the department, with each booking that could overlap a start in
    the window. No rows means the department has no active room."""
    rooms = Room.objects.filter(
        department_id=appointment_type.department_id, is_active=True
    ).annotate(
        booked=FilteredRelation(
            "appointment",
            condition=Q(
                appointment__status__in=ACTIVE_STATUSES,
                appointment__starts_at__lt=window.ends_at + duration,
                appointment__ends_at__gt=window.starts_at,
            ),
        )
    )
    rows = rooms.values_list("pk", "booked__starts_at", "booked__ends_at")
    return [
        (room_id, None if starts is None else TimeRange(starts, ends))
        for room_id, starts, ends in rows
    ]


def _with_free_room(
    offers: list[SlotOffer], slot_type: SlotType, room_rows: list[RoomRow]
) -> list[SlotOffer]:
    """Placement refuses a start when every active room is booked over it, so the offer must too."""
    room_count = len({room_id for room_id, _ in room_rows})
    booked = [(room_id, span) for room_id, span in room_rows if span is not None]
    return starts_with_free_room(offers, slot_type.duration, room_count, booked)


def _too_wide() -> Failure:
    return Failure.invalid_input([FieldMessage("to", "The range is at most 31 days.")])
