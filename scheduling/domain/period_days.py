"""Task 17c, #26: a period cut into the part that falls in each local day."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from scheduling.domain.workspace_day import local_day_bounds


@dataclass(frozen=True)
class DayPart:
    day: date
    starts_at: datetime
    ends_at: datetime
    whole_day: bool


def cut_into_days(
    starts_at: datetime, ends_at: datetime, days: Iterable[date], time_zone: str
) -> list[DayPart]:
    """Only days the period touches; a day's own bounds make 23 and 25 hour days right."""
    parts: list[DayPart] = []
    for day in days:
        day_start, day_end = local_day_bounds(day, time_zone)
        part_start = max(starts_at, day_start)
        part_end = min(ends_at, day_end)
        if part_start < part_end:
            whole_day = part_start == day_start and part_end == day_end
            parts.append(DayPart(day, part_start, part_end, whole_day))
    return parts
