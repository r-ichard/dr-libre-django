"""Sections 6.3 to 6.5 and 4: the address of a search is read leniently, an unusable value
falls back to its default instead of failing."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from uuid import UUID

MAXIMUM_TEXT_LENGTH = 100
PAGE_SIZES = (10, 20, 50)
DEFAULT_PAGE_SIZE = 20
WINDOWS = ("any", "today", "3_days", "7_days")
TIMES_OF_DAY = ("morning", "afternoon", "evening")
SORTS = ("soonest", "name_asc", "name_desc", "distance")
MAXIMUM_LATITUDE = 90.0
MAXIMUM_LONGITUDE = 180.0


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class SearchQuery:
    text: str
    specialty_id: UUID | None
    hospital_id: UUID | None
    city: str | None
    appointment_type_id: UUID | None
    earliest_date: date | None
    window: str
    time_of_day: str | None
    sort: str
    page: int
    page_size: int
    location: Location | None


def parse_search_query(raw: Mapping[str, str]) -> SearchQuery:
    location = _location(raw.get("latitude"), raw.get("longitude"))
    sort = raw.get("sort", "")
    return SearchQuery(
        text=raw.get("q", "").strip()[:MAXIMUM_TEXT_LENGTH].strip(),
        specialty_id=_uuid(raw.get("specialty")),
        hospital_id=_uuid(raw.get("hospital")),
        city=raw.get("city", "").strip() or None,
        appointment_type_id=_uuid(raw.get("appointment_type")),
        earliest_date=_date(raw.get("from")),
        window=_choice(raw.get("window"), WINDOWS) or "any",
        time_of_day=_choice(raw.get("time_of_day"), TIMES_OF_DAY),
        sort="soonest" if sort not in SORTS or (sort == "distance" and location is None) else sort,
        page=_page(raw.get("page")),
        page_size=_page_size(raw.get("page_size")),
        location=location,
    )


def _choice(value: str | None, choices: tuple[str, ...]) -> str | None:
    return value if value in choices else None


def _uuid(value: str | None) -> UUID | None:
    try:
        return None if value is None else UUID(value)
    except ValueError:
        return None


def _date(value: str | None) -> date | None:
    try:
        return None if value is None else date.fromisoformat(value)
    except ValueError:
        return None


def _page(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _page_size(value: str | None) -> int:
    try:
        size = int(value or "")
    except ValueError:
        return DEFAULT_PAGE_SIZE
    return size if size in PAGE_SIZES else DEFAULT_PAGE_SIZE


def _location(latitude: str | None, longitude: str | None) -> Location | None:
    try:
        point = Location(float(latitude or ""), float(longitude or ""))
    except ValueError:
        return None
    within = abs(point.latitude) <= MAXIMUM_LATITUDE and abs(point.longitude) <= MAXIMUM_LONGITUDE
    return point if within and math.isfinite(point.latitude + point.longitude) else None
