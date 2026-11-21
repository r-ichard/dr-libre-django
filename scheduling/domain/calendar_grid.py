"""Section 9.2: a time span to rows of the 07:00 to 19:00 grid of 30 minute rows (24 rows)."""

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo

GRID_START_MINUTE = 7 * 60
GRID_END_MINUTE = 19 * 60
ROW_MINUTES = 30
ROW_COUNT = (GRID_END_MINUTE - GRID_START_MINUTE) // ROW_MINUTES


@dataclass(frozen=True)
class GridPlacement:
    first_row: int
    span: int


def _minute_of_day(moment: datetime, zone: ZoneInfo) -> int:
    local = moment.astimezone(zone)
    return local.hour * 60 + local.minute


def place_in_grid(starts_at: datetime, ends_at: datetime, time_zone: str) -> GridPlacement | None:
    """None when the span starts outside the grid; an end past 19:00 is cut to the last row."""
    zone = ZoneInfo(time_zone)
    start_minute = _minute_of_day(starts_at, zone)
    if not GRID_START_MINUTE <= start_minute < GRID_END_MINUTE:
        return None
    first_row = (start_minute - GRID_START_MINUTE) // ROW_MINUTES + 1
    duration_minutes = (ends_at - starts_at).total_seconds() / 60
    span = max(1, ceil(duration_minutes / ROW_MINUTES))
    return GridPlacement(first_row, min(span, ROW_COUNT - first_row + 1))
