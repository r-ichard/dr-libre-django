"""Section 5.1, no clinician named: the union of free slots with who is free at each start."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import (
    AvailabilityWindow,
    BusyInterval,
    ExistingAppointment,
    SlotType,
    TimeRange,
    free_slots,
)

MAXIMUM_QUERY_DAYS = 31


@dataclass(frozen=True)
class ClinicianSchedule:
    rules: Sequence[AvailabilityWindow]
    time_off: Sequence[BusyInterval]
    appointments: Sequence[ExistingAppointment]


@dataclass(frozen=True)
class SlotOffer:
    start: datetime
    clinician_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class QueryTooWide:
    maximum_days: int


def free_slots_by_start(
    schedules: Mapping[UUID, ClinicianSchedule],
    appointment_type: SlotType,
    window: TimeRange,
    now: datetime,
    time_zone: ZoneInfo,
) -> list[SlotOffer] | QueryTooWide:
    if window.ends_at - window.starts_at > timedelta(days=MAXIMUM_QUERY_DAYS):
        return QueryTooWide(MAXIMUM_QUERY_DAYS)
    free_clinicians: dict[datetime, list[UUID]] = {}
    for clinician_id in sorted(schedules):
        schedule = schedules[clinician_id]
        starts = free_slots(
            schedule.rules,
            appointment_type,
            schedule.time_off,
            schedule.appointments,
            window,
            now,
            time_zone,
        )
        for start in starts:
            free_clinicians.setdefault(start, []).append(clinician_id)
    return [SlotOffer(start, tuple(ids)) for start, ids in sorted(free_clinicians.items())]


def starts_with_free_room(
    offers: list[SlotOffer],
    duration: timedelta,
    room_count: int,
    booked_rooms: Sequence[tuple[UUID, TimeRange]],
) -> list[SlotOffer]:
    """A start stays offered while fewer rooms are booked over its whole length than exist."""
    return [
        offer
        for offer in offers
        if _rooms_booked_over(offer.start, duration, booked_rooms) < room_count
    ]


def _rooms_booked_over(
    start: datetime, duration: timedelta, booked_rooms: Sequence[tuple[UUID, TimeRange]]
) -> int:
    return len(
        {
            room_id
            for room_id, span in booked_rooms
            if span.starts_at < start + duration and span.ends_at > start
        }
    )
