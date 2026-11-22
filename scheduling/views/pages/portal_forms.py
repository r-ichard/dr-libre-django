"""Task 15: what the portal's forms share: error values for the templates and strict parsers."""

import re
from datetime import date
from uuid import UUID

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure

ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
NOTICE_COOKIE = "drlibre_notice"
NOTICE_LIFETIME_SECONDS = 60


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


def redirect_with_notice(path: str, key: str) -> HttpResponseRedirect:
    """A notice comes from what the server just did, so it rides a short-lived cookie the next
    page takes once; an address value could be written by anyone."""
    response = HttpResponseRedirect(path, status=303)
    response.set_cookie(
        NOTICE_COOKIE,
        key,
        max_age=NOTICE_LIFETIME_SECONDS,
        httponly=True,
        samesite="Strict",
    )
    return response


def take_notice(request: HttpRequest, notices: dict[str, str]) -> str:
    """Text for the key the cookie holds; an unknown key is no notice."""
    return notices.get(request.COOKIES.get(NOTICE_COOKIE, ""), "")


def forget_notice(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    if NOTICE_COOKIE in request.COOKIES:
        response.delete_cookie(NOTICE_COOKIE, samesite="Strict")
    return response
