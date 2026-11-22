"""Section 4: the filters of the admin lists live in the address. A value that cannot be used
falls back to "no filter", never to an error page."""

from collections.abc import Container, Mapping
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from uuid import UUID

from django.http import HttpRequest

from scheduling.models import User
from scheduling.views.pages.booking_links import week_from

MAXIMUM_PAGE_DIGITS = 6
MAXIMUM_SEARCH_LENGTH = 100


@dataclass(frozen=True)
class DayRange:
    first: date | None
    last: date | None


def page_number(request: HttpRequest) -> int:
    raw = request.GET.get("page", "")
    usable = raw.isascii() and raw.isdigit() and len(raw) <= MAXIMUM_PAGE_DIGITS
    return int(raw) if usable else 1


def uuid_param(request: HttpRequest, name: str) -> UUID | None:
    try:
        return UUID(request.GET.get(name, ""))
    except ValueError:
        return None


def choice_param(request: HttpRequest, name: str, allowed: Container[str]) -> str:
    raw = request.GET.get(name, "")
    return raw if raw in allowed else ""


def day_range(request: HttpRequest) -> DayRange:
    first = week_from(request.GET.get("from", ""))
    last = week_from(request.GET.get("to", ""))
    if first is not None and last is not None and first > last:
        return DayRange(None, None)
    return DayRange(first, last)


def address_with(base_path: str, filters: Mapping[str, str], page: int = 1) -> str:
    """The list address with the filters that are set, and the page when it is not the first."""
    kept = {name: value for name, value in filters.items() if value}
    if page > 1:
        kept["page"] = str(page)
    return f"{base_path}?{urlencode(kept)}" if kept else base_path


def page_links(
    base_path: str, filters: Mapping[str, str], page: int, page_count: int
) -> dict[str, str]:
    """Context entries for the previous and next links; empty at either end."""
    return {
        "previous_href": address_with(base_path, filters, page - 1) if page > 1 else "",
        "next_href": address_with(base_path, filters, page + 1) if page < page_count else "",
    }


def search_text(request: HttpRequest) -> str:
    """The patient search text: trimmed, no null bytes, capped."""
    return request.GET.get("q", "").replace("\x00", "").strip()[:MAXIMUM_SEARCH_LENGTH]


def patient_links(patients: list[User], next_path: str) -> list[dict[str, str]]:
    """Search results as links that carry the chosen patient's id to the next step."""
    return [
        {
            "name": person.full_name,
            "email": person.email,
            "href": f"{next_path}?patient={person.pk}",
        }
        for person in patients
    ]
