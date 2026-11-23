"""Sections 6.1 to 6.3: text match, the range slots are looked for, and time of day."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.booking_rules import LEAD_TIME
from scheduling.domain.free_slots import TimeRange

HORIZON = timedelta(days=90)
WINDOW_DAYS = {"3_days": 3, "7_days": 7}
NOON = time(12, 0)
LAST_AFTERNOON_MOMENT = time(17, 0)


@dataclass(frozen=True)
class ProviderRecord:
    id: UUID
    full_name: str
    title: str
    hospital_name: str
    city: str
    time_zone: str
    specialty_name: str
    department_name: str
    type_names: tuple[str, ...]


def matches_text(text: str, provider: ProviderRecord) -> bool:
    wanted = text.casefold()
    searched = (
        provider.hospital_name,
        provider.city,
        provider.full_name,
        provider.specialty_name,
        provider.department_name,
        *provider.type_names,
    )
    return any(wanted in field.casefold() for field in searched)


def search_range(
    now: datetime, time_zone: ZoneInfo, window: str, earliest_date: date | None
) -> TimeRange | None:
    start = now + LEAD_TIME
    if earliest_date is not None:
        start = max(start, _local_midnight(earliest_date, time_zone))
    end = now + HORIZON
    if window == "today":
        end = min(
            end, _local_midnight(now.astimezone(time_zone).date() + timedelta(days=1), time_zone)
        )
    if window in WINDOW_DAYS:
        end = min(end, now + timedelta(days=WINDOW_DAYS[window]))
    return TimeRange(start, end) if start < end else None


def time_of_day_of(start: datetime, time_zone: ZoneInfo) -> str:
    local = start.astimezone(time_zone).time()
    if local < NOON:
        return "morning"
    return "afternoon" if local <= LAST_AFTERNOON_MOMENT else "evening"


def _local_midnight(day: date, time_zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=time_zone).astimezone(UTC)
