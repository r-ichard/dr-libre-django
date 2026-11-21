"""One time grid for the clinician's calendar (columns are days) and the rooms timeline (columns
are rooms): the 07:00 to 19:00 axis, and the placement of each item on its column's rows."""

from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.calendar_grid import HOUR_LABELS, ROW_COUNT, place_in_grid

OUTSIDE_GRID = "Outside 07:00 to 19:00"


@dataclass(frozen=True)
class GridItem:
    """Lines are read top to bottom: time first, then what and who."""

    starts_at: datetime
    ends_at: datetime
    lines: tuple[str, ...]
    href: str
    classes: str
    badge: tuple[str, str] | None


def axis_rows() -> list[str]:
    """A label on the hour rows, blank on the half hours."""
    return [HOUR_LABELS[row // 2] if row % 2 == 0 else "" for row in range(ROW_COUNT)]


def grid_column(
    heading: str,
    spoken: str,
    items: list[GridItem],
    window: tuple[datetime, datetime],
    time_zone: str,
) -> dict[str, object]:
    """Items overlapping the window, cut to it, split into those on the grid and those outside."""
    window_start, window_end = window
    inside: list[dict[str, object]] = []
    outside: list[dict[str, object]] = []
    for item in items:
        if item.starts_at >= window_end or item.ends_at <= window_start:
            continue
        placement = place_in_grid(
            max(item.starts_at, window_start), min(item.ends_at, window_end), time_zone
        )
        shown = {"lines": item.lines, "href": item.href, "badge": item.badge}
        if placement is None:
            outside.append({**shown, "classes": item.classes})
        else:
            grid = f"time-grid-at-{placement.first_row} time-grid-span-{placement.span}"
            inside.append({**shown, "classes": f"{grid} {item.classes}"})
    return {
        "heading": heading,
        "spoken": spoken,
        "inside": inside,
        "outside": outside,
        "outside_title": OUTSIDE_GRID,
    }
