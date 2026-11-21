"""Sections 6.4 and 6.5: sorting over the whole result set, then the page is cut."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

EARTH_RADIUS_KILOMETRES = 6371.0088


@dataclass(frozen=True)
class Sortable:
    id: UUID
    name: str
    first_start: datetime | None
    distance: float | None


@dataclass(frozen=True)
class Page[Item]:
    items: list[Item]
    total: int
    page: int
    page_count: int


def sort_results(items: Sequence[Sortable], sort: str) -> list[Sortable]:
    by_name = sorted(items, key=lambda item: (item.name.casefold(), item.id))
    if sort == "name_asc":
        return by_name
    if sort == "name_desc":
        # Reverse keeps equal names in id order, since the sort is stable.
        return sorted(
            sorted(items, key=lambda item: item.id),
            key=lambda item: item.name.casefold(),
            reverse=True,
        )
    if sort == "distance":
        return sorted(by_name, key=lambda item: (item.distance is None, item.distance or 0.0))
    return sorted(by_name, key=lambda item: (item.first_start is None, item.first_start or _NEVER))


_NEVER = datetime.max.replace(tzinfo=UTC)


def haversine_kilometres(
    from_latitude: float, from_longitude: float, to_latitude: float, to_longitude: float
) -> float:
    delta_latitude = math.radians(to_latitude - from_latitude)
    delta_longitude = math.radians(to_longitude - from_longitude)
    half_chord = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(math.radians(from_latitude))
        * math.cos(math.radians(to_latitude))
        * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KILOMETRES * math.asin(math.sqrt(half_chord))


def paginate[Item](items: Sequence[Item], page: int, page_size: int) -> Page[Item]:
    page_count = max(1, math.ceil(len(items) / page_size))
    shown = min(page, page_count)
    first = (shown - 1) * page_size
    return Page(list(items[first : first + page_size]), len(items), shown, page_count)
