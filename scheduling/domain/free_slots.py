"""Section 5.1: free slots of one clinician, in the hospital's local time."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.appointment_status import is_active
from scheduling.models.booking import AppointmentStatus

DAYS_PER_WEEK = 7


@dataclass(frozen=True)
class AvailabilityWindow:
    weekday: int
    start_time: time
    end_time: time
    slot_step: timedelta
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True)
class SlotType:
    duration: timedelta
    buffer: timedelta


@dataclass(frozen=True)
class TimeRange:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class BusyInterval:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class ExistingAppointment:
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus


def free_slots(
    rules: Sequence[AvailabilityWindow],
    appointment_type: SlotType,
    time_off: Sequence[BusyInterval],
    appointments: Sequence[ExistingAppointment],
    window: TimeRange,
    now: datetime,
    time_zone: ZoneInfo,
) -> list[datetime]:
    blocked = [(off.starts_at, off.ends_at) for off in time_off] + [
        (booked.starts_at, booked.ends_at + appointment_type.buffer)
        for booked in appointments
        if is_active(booked.status)
    ]
    starts: set[datetime] = set()
    for day in _local_days(window, time_zone):
        for rule in rules:
            if not _rule_applies(rule, day):
                continue
            for start in _rule_starts(rule, day, appointment_type, time_zone):
                end = start + appointment_type.duration
                if start < window.starts_at or end > window.ends_at or start < now:
                    continue
                if any(start < stop and begin < end for begin, stop in blocked):
                    continue
                starts.add(start)
    return sorted(starts)


def _local_days(window: TimeRange, time_zone: ZoneInfo) -> list[date]:
    first = window.starts_at.astimezone(time_zone).date()
    last = window.ends_at.astimezone(time_zone).date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _rule_applies(rule: AvailabilityWindow, day: date) -> bool:
    # The stored weekday counts from Sunday = 0, Python's isoweekday has Sunday = 7.
    weekday = day.isoweekday() % DAYS_PER_WEEK
    return (
        rule.weekday == weekday
        and rule.valid_from <= day
        and (rule.valid_to is None or day <= rule.valid_to)
    )


def _rule_starts(
    rule: AvailabilityWindow, day: date, appointment_type: SlotType, time_zone: ZoneInfo
) -> list[datetime]:
    # Stepping in naive local time keeps the rule's wall-clock bounds across clock changes.
    starts: list[datetime] = []
    local_start = datetime.combine(day, rule.start_time)
    local_end = datetime.combine(day, rule.end_time)
    while local_start + appointment_type.duration <= local_end:
        start = _to_utc_if_it_exists(local_start, time_zone)
        if start is not None:
            starts.append(start)
        local_start += rule.slot_step
    return starts


def _to_utc_if_it_exists(local_start: datetime, time_zone: ZoneInfo) -> datetime | None:
    # fold=0 picks the first occurrence of a repeated time; a skipped time changes on round trip.
    aware = local_start.replace(tzinfo=time_zone, fold=0)
    instant = aware.astimezone(UTC)
    if instant.astimezone(time_zone).replace(tzinfo=None) != local_start:
        return None
    return instant
