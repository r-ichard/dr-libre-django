"""Task 15: what the portal's forms share: error values for the templates and strict parsers."""

import re
from datetime import date
from uuid import UUID

from scheduling.domain.failure import Failure

ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
NOTICE_KEY = "notice"


def failure_messages(failure: Failure) -> dict[str, str]:
    """Field name to message; the first message of a field wins."""
    fields = failure.details.get("fields")
    messages: dict[str, str] = {}
    for item in fields if isinstance(fields, list) else []:
        messages.setdefault(str(item["field"]), str(item["message"]))
    return messages


def summary_items(messages: dict[str, str]) -> list[dict[str, str]]:
    return [{"target": f"id_{name}", "message": text} for name, text in messages.items()]


def day_or_none(raw: str) -> date | None:
    if not ISO_DAY.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def uuid_or_none(raw: str) -> UUID | None:
    try:
        return UUID(raw)
    except ValueError:
        return None
