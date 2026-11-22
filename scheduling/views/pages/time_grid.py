"""One time grid for the clinician's calendar (columns are days) and the rooms timeline (columns
are rooms): the 07:00 to 19:00 axis, and the placement of each item on its column's rows."""

from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.calendar_grid import (
    HOUR_LABELS,
    ROW_COUNT,
    GridPlacement,
    lines_that_fit,
    place_in_grid,
)
from scheduling.domain.lane_assignment import assign_lanes, covered_by

OUTSIDE_GRID = "Outside 07:00 to 19:00"
LANE_LIMIT = 8


@dataclass(frozen=True)
class GridItem:
    """Lines are read top to bottom: time first, then what and who."""

    starts_at: datetime
    ends_at: datetime
    lines: tuple[str, ...]
    href: str
    classes: str
    badge: tuple[str, str] | None
    behind: bool = False


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
    placed: list[tuple[GridItem, GridPlacement]] = []
    outside: list[dict[str, object]] = []
    for item in items:
        if item.starts_at >= window_end or item.ends_at <= window_start:
            continue
        placement = place_in_grid(
            max(item.starts_at, window_start), min(item.ends_at, window_end), time_zone
        )
        if placement is None:
            outside.append({**_shown(item), "classes": item.classes, "fits": len(item.lines)})
        else:
            placed.append((item, placement))
    return {
        "heading": heading,
        "spoken": spoken,
        "inside": _inside(placed),
        "outside": outside,
        "outside_title": OUTSIDE_GRID,
    }


def _shown(item: GridItem) -> dict[str, object]:
    return {
        "lines": item.lines,
        "href": item.href,
        "badge": item.badge,
        "spoken": ", ".join(item.lines),
    }


def _rows(placement: GridPlacement) -> tuple[int, int]:
    return placement.first_row, placement.first_row + placement.span


def _inside(placed: list[tuple[GridItem, GridPlacement]]) -> list[dict[str, object]]:
    lane_classes = _lane_classes(placed)
    return [
        {
            **_shown(item),
            "classes": (
                f"time-grid-at-{place.first_row} time-grid-span-{place.span} "
                f"{lane_classes[position]} {item.classes}"
            ),
            "fits": lines_that_fit(place.span),
        }
        for position, (item, place) in enumerate(placed)
    ]


def _lane_classes(placed: list[tuple[GridItem, GridPlacement]]) -> list[str]:
    """Lanes are decided per layer: the band behind and the appointments in front of it."""
    bands = [_rows(place) for item, place in placed if item.behind]
    classes = [""] * len(placed)
    for behind in (True, False):
        positions = [n for n, (item, _) in enumerate(placed) if item.behind is behind]
        rows = [_rows(placed[n][1]) for n in positions]
        covered = [False] * len(rows) if behind else covered_by(rows, bands)
        for position, lane, over in zip(positions, assign_lanes(rows), covered, strict=True):
            layer = "time-grid-behind" if behind else "time-grid-front"
            number = min(lane.lane, LANE_LIMIT)
            count = min(lane.lane_count, LANE_LIMIT)
            classes[position] = (
                f"{layer}{' time-grid-over' if over else ''}"
                f" time-grid-lane-{number} time-grid-lanes-{count}"
            )
    return classes
