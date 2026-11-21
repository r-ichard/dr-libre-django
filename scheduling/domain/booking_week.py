"""Week strip arithmetic: Monday to Sunday in the hospital's time zone."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import DAYS_PER_WEEK, TimeRange


def week_range(day: date, time_zone: ZoneInfo) -> TimeRange:
    monday = day - timedelta(days=day.weekday())
    return TimeRange(
        _local_midnight(monday, time_zone), _local_midnight(next_week_start(monday), time_zone)
    )


def previous_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday() + DAYS_PER_WEEK)


def next_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday()) + timedelta(days=DAYS_PER_WEEK)


def group_by_local_day(
    slots: Sequence[datetime], time_zone: ZoneInfo
) -> dict[date, list[datetime]]:
    days: dict[date, list[datetime]] = defaultdict(list)
    for slot in sorted(slots):
        days[slot.astimezone(time_zone).date()].append(slot)
    return dict(days)


def _local_midnight(day: date, time_zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=time_zone).astimezone(UTC)
