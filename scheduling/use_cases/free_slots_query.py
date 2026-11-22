"""Section 5.1 and 14 GET /slots: the free slots of one clinician or of a whole department."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.slot_search import (
    MAXIMUM_QUERY_DAYS,
    QueryTooWide,
    SlotOffer,
    free_slots_by_start,
)
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
    clinicians = department_clinicians(appointment_type, clinician_id, online_only)
    clinician_ids = list(clinicians.values_list("pk", flat=True))
    if clinician_id is not None and not clinician_ids:
        return Failure.not_found()
    now = current_request_context().now
    slot_type = slot_type_of(appointment_type)
    schedules = load_schedules(clinician_ids, slot_type, window, now)
    time_zone_name = appointment_type.department.hospital.time_zone
    offers = free_slots_by_start(schedules, slot_type, window, now, ZoneInfo(time_zone_name))
    if isinstance(offers, QueryTooWide):
        return _too_wide()
    return Success(FoundSlots(offers, slot_type.duration, time_zone_name))


def _too_wide() -> Failure:
    return Failure.invalid_input([FieldMessage("to", "The range is at most 31 days.")])
