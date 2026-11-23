"""View-models of the provider, hospital and specialty pages. Every link is built from
ids the use case returned, never from the request."""

from datetime import date
from urllib.parse import urlencode

from scheduling.domain.search_address import search_href
from scheduling.domain.search_query import SearchQuery
from scheduling.domain.specialty_icons import icon_file_for
from scheduling.use_cases.booking_page_data import WeekOfSlots
from scheduling.use_cases.public_details import HospitalDetail, ProviderDetail, SpecialtyDetail
from scheduling.views.pages.booking_links import times_href
from scheduling.views.pages.booking_times import week_strip
from scheduling.views.pages.search_context import (
    hospital_href,
    page_size_links,
    provider_name,
    provider_row,
    specialty_href,
)


def provider_context(detail: ProviderDetail, week: WeekOfSlots) -> dict[str, object]:
    result = detail.provider
    path = f"/providers/{result.id}"

    def week_href(week_start: date) -> str:
        query = urlencode({"type": str(detail.chosen_type.id), "week": week_start.isoformat()})
        return f"{path}?{query}"

    row = provider_row(result)
    return {
        "provider": result,
        "name": provider_name(result),
        "bio": detail.bio,
        "hospital_href": hospital_href(result.hospital_id),
        "specialty_href": specialty_href(result.specialty_id),
        "slots": row["slots"],
        "switch": [
            {
                "label": f"{item.name}, {item.duration_minutes} minutes",
                "href": f"{path}?{urlencode({'type': str(item.id)})}",
                "current": item.id == detail.chosen_type.id,
            }
            for item in detail.appointment_types
        ],
        **week_strip(week, week_href),
    }


def hospital_context(detail: HospitalDetail) -> dict[str, object]:
    return {
        "hospital": detail,
        "rows": [provider_row(result) for result in detail.providers],
        "specialties": [
            {"name": item.name, "href": specialty_href(item.id)} for item in detail.specialties
        ],
        "first_available": [
            {
                "href": times_href(choice.appointment_type.id, None),
                "type_name": choice.appointment_type.name,
                "department_name": choice.department_name,
            }
            for choice in detail.first_available
        ],
    }


def specialty_context(detail: SpecialtyDetail, query: SearchQuery) -> dict[str, object]:
    found = detail.providers
    path = specialty_href(detail.specialty.id)
    return {
        "specialty": detail.specialty,
        "icon": icon_file_for(detail.specialty.code),
        "rows": [provider_row(result) for result in found.results],
        "page": found.page,
        "page_count": found.page_count,
        "previous_href": (
            search_href(query, "providers", path=path, page=found.page - 1)
            if found.page > 1
            else ""
        ),
        "next_href": (
            search_href(query, "providers", path=path, page=found.page + 1)
            if found.page < found.page_count
            else ""
        ),
        "page_sizes": page_size_links(query, "providers", path),
    }
