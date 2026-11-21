"""Task 10a: the view-model of the search page. Every link is rebuilt from the parsed query."""

from uuid import UUID

from scheduling.domain.search_address import LIST_KINDS, search_href
from scheduling.domain.search_query import PAGE_SIZES, SearchQuery, parse_search_query
from scheduling.domain.slot_text import slot_spoken_text, slot_visible_text
from scheduling.domain.specialty_icons import icon_file_for
from scheduling.use_cases.search_filter_options import FilterOptions
from scheduling.use_cases.search_types import (
    AnyResult,
    HospitalResult,
    Opening,
    ProviderResult,
    SearchPage,
    SpecialtyResult,
)
from scheduling.views.pages.booking_links import details_href, times_href

ANY = ("", "Any")
WINDOW_CHOICES = [
    ANY,
    ("today", "Today"),
    ("3_days", "Next 3 days"),
    ("7_days", "Next 7 days"),
]
TIME_OF_DAY_CHOICES = [
    ANY,
    ("morning", "Morning"),
    ("afternoon", "Afternoon"),
    ("evening", "Evening"),
]
SORT_CHOICES = [("soonest", "Soonest"), ("name_asc", "Name A to Z"), ("name_desc", "Name Z to A")]
DISTANCE_CHOICE = ("distance", "Nearest")


def search_context(
    kind: str, query: SearchQuery, found: SearchPage[AnyResult], options: FilterOptions
) -> dict[str, object]:
    return {
        "kind": kind,
        "query": query,
        "rows": [_row(result) for result in found.results],
        "total": found.total,
        "page": found.page,
        "page_count": found.page_count,
        "previous_href": search_href(query, kind, page=found.page - 1) if found.page > 1 else "",
        "next_href": (
            search_href(query, kind, page=found.page + 1) if found.page < found.page_count else ""
        ),
        "switch": [
            {
                "label": label,
                "href": search_href(query, name),
                "current": name == kind,
            }
            for name, label in zip(
                LIST_KINDS, ("Providers", "Hospitals", "Specialties"), strict=True
            )
        ],
        "page_sizes": [
            {
                "size": size,
                "href": search_href(query, kind, page_size=size),
                "current": size == query.page_size,
            }
            for size in PAGE_SIZES
        ],
        "widen_href": search_href(parse_search_query({"q": query.text}), kind),
        "fields": _fields(query, options),
        "location": query.location,
    }


def _fields(query: SearchQuery, options: FilterOptions) -> dict[str, object]:
    sorts = [*SORT_CHOICES, DISTANCE_CHOICE] if query.location else SORT_CHOICES
    return {
        "specialties": [ANY, *_choices(options.specialties)],
        "specialty": _text(query.specialty_id),
        "hospitals": [ANY, *_choices(options.hospitals)],
        "hospital": _text(query.hospital_id),
        "cities": [ANY, *((city, city) for city in options.cities)],
        "city": query.city or "",
        "types": [ANY, *_choices(options.appointment_types)],
        "appointment_type": _text(query.appointment_type_id),
        "from": query.earliest_date.isoformat() if query.earliest_date else "",
        "windows": WINDOW_CHOICES,
        "window": "" if query.window == "any" else query.window,
        "times_of_day": TIME_OF_DAY_CHOICES,
        "time_of_day": query.time_of_day or "",
        "sorts": sorts,
        "sort": query.sort,
    }


def _choices(pairs: list[tuple[UUID, str]]) -> list[tuple[str, str]]:
    return [(str(identifier), name) for identifier, name in pairs]


def _text(identifier: UUID | None) -> str:
    return str(identifier) if identifier else ""


def _row(result: AnyResult) -> dict[str, object]:
    if isinstance(result, ProviderResult):
        return _provider_row(result)
    if isinstance(result, HospitalResult):
        return {"hospital": result, "opening": _opening(result.earliest)}
    return _specialty_row(result)


def _provider_row(result: ProviderResult) -> dict[str, object]:
    name = f"{result.title} {result.full_name}".strip()
    slots = [
        {
            "visible": slot_visible_text(start, result.time_zone),
            "spoken": slot_spoken_text(start, result.time_zone, name),
            "href": details_href(result.appointment_type_id, result.id, start),
        }
        for start in result.next_starts
    ]
    return {
        "provider": result,
        "name": name,
        "slots": slots,
        "times_href": times_href(result.appointment_type_id, result.id),
    }


def _specialty_row(result: SpecialtyResult) -> dict[str, object]:
    code = result.name.casefold().replace(" ", "-")
    return {
        "specialty": result,
        "icon": icon_file_for(code),
        "opening": _opening(result.earliest),
    }


def _opening(earliest: Opening | None) -> dict[str, object] | None:
    if earliest is None:
        return None
    return {
        "visible": slot_visible_text(earliest.starts_at, earliest.time_zone),
        "spoken": slot_spoken_text(
            earliest.starts_at, earliest.time_zone, "the earliest available provider"
        ),
        "href": details_href(
            earliest.appointment_type_id, earliest.clinician_id, earliest.starts_at
        ),
        "time_zone": earliest.time_zone,
    }
