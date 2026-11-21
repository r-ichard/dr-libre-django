"""Task 10a: the view-model of the search page. Every link is rebuilt from the parsed query."""

from uuid import UUID

from scheduling.domain.search_address import LIST_KINDS, has_filters, search_href, widened_query
from scheduling.domain.search_query import PAGE_SIZES, SearchQuery
from scheduling.domain.slot_text import slot_visible_text
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
        "page_sizes": page_size_links(query, kind),
        "widen_href": _widen_href(query, kind),
        "filters_set": has_filters(query),
        "fields": _fields(query, options),
        "location": query.location,
    }


def page_size_links(query: SearchQuery, kind: str, path: str = "/") -> list[dict[str, object]]:
    return [
        {
            "size": size,
            "href": search_href(query, kind, path=path, page_size=size),
            "current": size == query.page_size,
        }
        for size in PAGE_SIZES
    ]


def _widen_href(query: SearchQuery, kind: str) -> str:
    wider = widened_query(query)
    return "" if wider == query else search_href(wider, kind)


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
        return provider_row(result)
    if isinstance(result, HospitalResult):
        return {
            "hospital": result,
            "hospital_href": hospital_href(result.id),
            "opening": _opening(result.earliest),
        }
    return _specialty_row(result)


def provider_name(result: ProviderResult) -> str:
    return f"{result.title} {result.full_name}".strip()


def provider_row(result: ProviderResult) -> dict[str, object]:
    slots = [
        {
            "visible": slot_visible_text(start, result.time_zone),
            "href": details_href(result.appointment_type_id, result.id, start),
        }
        for start in result.next_starts
    ]
    return {
        "provider": result,
        "name": provider_name(result),
        "provider_href": f"/providers/{result.id}",
        "hospital_href": hospital_href(result.hospital_id),
        "specialty_href": specialty_href(result.specialty_id),
        "slots": slots,
        "times_href": times_href(result.appointment_type_id, result.id),
    }


def _specialty_row(result: SpecialtyResult) -> dict[str, object]:
    return {
        "specialty": result,
        "specialty_href": specialty_href(result.id),
        "icon": icon_file_for(result.code),
        "opening": _opening(result.earliest),
    }


def _opening(earliest: Opening | None) -> dict[str, object] | None:
    if earliest is None:
        return None
    return {
        "visible": slot_visible_text(earliest.starts_at, earliest.time_zone),
        "href": details_href(
            earliest.appointment_type_id, earliest.clinician_id, earliest.starts_at
        ),
        "provider_name": "the earliest available provider",
        "time_zone": earliest.time_zone,
    }


def hospital_href(hospital_id: UUID) -> str:
    return f"/hospitals/{hospital_id}"


def specialty_href(specialty_id: UUID) -> str:
    return f"/specialties/{specialty_id}"
