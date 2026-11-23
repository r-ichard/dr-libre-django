"""Section 5.1 and 14 GET /slots: the free slots of one clinician or of a whole department."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.booking_rules import earliest_offered_start
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.slot_search import (
    MAXIMUM_QUERY_DAYS,
    QueryTooWide,
    SlotOffer,
    free_slots_by_start,
)
from scheduling.models import AppointmentType, Room
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import (
    active_appointment_type,
    department_clinicians,
    load_schedules,
    slot_type_of,
)


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
    if _lacks_room(appointment_type):
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
    return Success(FoundSlots(offers, slot_type.duration, time_zone_name))


def _lacks_room(appointment_type: AppointmentType) -> bool:
    """A type that needs a room has nothing to offer while its department has no active room."""
    active_rooms = Room.objects.filter(department_id=appointment_type.department_id, is_active=True)
    return appointment_type.needs_room and not active_rooms.exists()


def _too_wide() -> Failure:
    return Failure.invalid_input([FieldMessage("to", "The range is at most 31 days.")])
