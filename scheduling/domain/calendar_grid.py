"""Section 9.2: a time span to rows of the 07:00 to 19:00 grid of 30 minute rows (24 rows)."""

from dataclasses import dataclass
from datetime import datetime
from math import ceil
from zoneinfo import ZoneInfo

GRID_START_MINUTE = 7 * 60
GRID_END_MINUTE = 19 * 60
ROW_MINUTES = 30
ROW_COUNT = (GRID_END_MINUTE - GRID_START_MINUTE) // ROW_MINUTES
ROW_HEIGHT_PIXELS = 68
LINE_HEIGHT_PIXELS = 18
BLOCK_FRAME_PIXELS = 12
HOUR_LABELS = tuple(
    f"{hour:02d}:00" for hour in range(GRID_START_MINUTE // 60, GRID_END_MINUTE // 60 + 1)
)


@dataclass(frozen=True)
class GridPlacement:
    first_row: int
    span: int


def _minute_of_day(moment: datetime, zone: ZoneInfo) -> int:
    local = moment.astimezone(zone)
    return local.hour * 60 + local.minute


def place_in_grid(starts_at: datetime, ends_at: datetime, time_zone: str) -> GridPlacement | None:
    """Rows the span covers once cut to the grid; None when it does not touch 07:00 to 19:00."""
    start_minute = _minute_of_day(starts_at, ZoneInfo(time_zone))
    duration_minutes = (ends_at - starts_at).total_seconds() / 60
    end_minute = start_minute + duration_minutes
    if start_minute >= GRID_END_MINUTE or (
        end_minute <= GRID_START_MINUTE and start_minute < GRID_START_MINUTE
    ):
        return None
    shown_start = max(start_minute, GRID_START_MINUTE)
    shown_end = min(end_minute, GRID_END_MINUTE)
    first_row = (shown_start - GRID_START_MINUTE) // ROW_MINUTES + 1
    span = max(1, ceil((shown_end - shown_start) / ROW_MINUTES))
    return GridPlacement(first_row, min(span, ROW_COUNT - first_row + 1))


def lines_that_fit(span_rows: int) -> int:
    """Whole lines a block of this many rows holds after its margin, border and padding."""
    return (ROW_HEIGHT_PIXELS * span_rows - BLOCK_FRAME_PIXELS) // LINE_HEIGHT_PIXELS
