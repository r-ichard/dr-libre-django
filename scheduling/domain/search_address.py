"""Section 6.5: every state of a search lives in the address, rebuilt from the parsed query so a
shared link holds only known keys."""

from dataclasses import replace
from urllib.parse import urlencode

from scheduling.domain.search_query import DEFAULT_PAGE_SIZE, SearchQuery

LIST_KINDS = ("providers", "hospitals", "specialties")


def parse_list_kind(raw: str) -> str:
    return raw if raw in LIST_KINDS else LIST_KINDS[0]


def search_href(query: SearchQuery, kind: str, **changes: object) -> str:
    # Callers name SearchQuery fields; mypy cannot check a spread of keywords.
    changed = replace(query, **{"page": 1, **changes})  # type: ignore[arg-type]
    keeps_size = "page_size" in changes or changed.page_size != DEFAULT_PAGE_SIZE
    pairs = [
        ("q", changed.text),
        ("list", "" if kind == LIST_KINDS[0] else kind),
        ("specialty", changed.specialty_id or ""),
        ("hospital", changed.hospital_id or ""),
        ("city", changed.city or ""),
        ("appointment_type", changed.appointment_type_id or ""),
        ("from", changed.earliest_date or ""),
        ("window", "" if changed.window == "any" else changed.window),
        ("time_of_day", changed.time_of_day or ""),
        ("sort", "" if changed.sort == "soonest" else changed.sort),
        ("page", "" if changed.page == 1 else changed.page),
        ("page_size", changed.page_size if keeps_size else ""),
        ("latitude", changed.location.latitude if changed.location else ""),
        ("longitude", changed.location.longitude if changed.location else ""),
    ]
    given = [(key, str(value)) for key, value in pairs if value != ""]
    return f"/?{urlencode(given)}" if given else "/"
