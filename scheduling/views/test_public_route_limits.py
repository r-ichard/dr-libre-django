"""Section 14: every route answering without session or token has a limit or a reason."""

import re
import uuid
from collections.abc import Iterator

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.domain.rate_limit_rules import RATE_LIMITS, RateLimit
from scheduling.views.api_clients import browser_api_client
from scheduling.views.api_view import ApiView

pytestmark = pytest.mark.django_db

METHODS = ("get", "post")
NOT_PUBLIC_STATUSES = {401, 403, 405}
ONE_HIT = RateLimit(per_email=1, per_address=1)
FHIR_SEARCH_ROUTE = r"^fhir/"
FHIR_SEARCH_PATH = "/fhir/Location"
WRITE_REASON = "write: needs a body and, past that, a session or token; computes no schedule"

COSTS_NOTHING = {
    "api/v1/health": "health check: one constant answer",
    "favicon.ico": "redirect to a static file",
    "terms": "static text page",
    "privacy": "static text page",
    "sign-in": "form page; password failures have their own lockout (task 12)",
    "sign-in/check-email": "static text page",
    "sign-in/link": "form page; the link itself is one use and has its own limit",
    "fhir": "bare entry: no resource, answers 404 without computing anything",
    r"^static/(?P<path>.*)$": "file server: no schedule, no database",
}
OWN_LIMIT = {
    "api/v1/auth/login": "password failures have their own lockout (task 12)",
    "api/v1/auth/logout": WRITE_REASON,
    "api/v1/auth/link": "link requests are limited per email and address (task 12)",
    "api/v1/auth/link/verify": "link use is one-shot and limited (task 12)",
    "api/v1/booking/holds": "hold requests are limited per email and address (task 12)",
    "api/v1/booking/holds/<uuid:hold_id>/resend": "code requests are limited (task 12)",
    "api/v1/booking/holds/<uuid:hold_id>/verify": "code attempts are limited (task 12)",
    "sign-in/email-link": "link requests are limited per email and address (task 12)",
    "book/holds/<uuid:hold_id>/code": "code attempts are limited (task 12)",
    "book/holds/<uuid:hold_id>/resend": "code requests are limited (task 12)",
    "book/<uuid:appointment_type_id>/details": "hold requests are limited (task 12)",
    "api/v1/appointments": WRITE_REASON,
    "api/v1/appointments/<uuid:appointment_id>/cancel": WRITE_REASON,
    "api/v1/appointments/<uuid:appointment_id>/reschedule": WRITE_REASON,
    "api/v1/appointments/<uuid:appointment_id>/check-in": WRITE_REASON,
    "api/v1/appointments/<uuid:appointment_id>/complete": WRITE_REASON,
    "api/v1/appointments/<uuid:appointment_id>/no-show": WRITE_REASON,
    "api/v1/waitlist": WRITE_REASON,
    "api/v1/waitlist/<uuid:entry_id>/accept": WRITE_REASON,
    "api/v1/waitlist/<uuid:entry_id>/offer": WRITE_REASON,
    "api/v1/jobs/reminders": "admin-only job: refuses a caller without an admin session or token",
}
REASONS = COSTS_NOTHING | OWN_LIMIT


def _routes(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, URLPattern]]:
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _routes(list(pattern.url_patterns), route)
        else:
            yield route, pattern


def _path(route: str) -> str:
    if route == FHIR_SEARCH_ROUTE:
        return FHIR_SEARCH_PATH
    filled = re.sub(r"<uuid:\w+>", str(uuid.uuid4()), route)
    return "/" + re.sub(r"\(\?P<path>\.\*\)", "x", filled).strip("^$")


def _answers(client: Client, method: str, route: str) -> tuple[int, int, str]:
    path = _path(route)
    first = getattr(client, method)(path)
    second = getattr(client, method)(path)
    return first.status_code, second.status_code, first.get("Location", "")


def _unlimited_public_routes() -> set[str]:
    client = browser_api_client(raise_request_exception=False)
    found: set[str] = set()
    for route, pattern in _routes(list(get_resolver().url_patterns)):
        view_class = getattr(pattern.callback, "cls", None)
        for method in METHODS:
            is_api = isinstance(view_class, type) and issubclass(view_class, ApiView)
            if is_api and not hasattr(view_class, method):
                continue
            first, second, location = _answers(client, method, route)
            sign_in_redirect = first == 302 and "/sign-in" in location
            if first in NOT_PUBLIC_STATUSES or sign_in_redirect or second == 429:
                continue
            found.add(route)
    return found


def returns_a_limit_or_a_reason_for_every_route_that_answers_without_a_session_or_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for scope in RATE_LIMITS:
        monkeypatch.setitem(RATE_LIMITS, scope, ONE_HIT)

    unlimited = _unlimited_public_routes()

    assert sorted(unlimited - REASONS.keys()) == []


def returns_no_stale_entry_when_every_listed_route_is_in_the_url_configuration() -> None:
    known = {route for route, _ in _routes(list(get_resolver().url_patterns))}

    assert sorted(REASONS.keys() - known) == []
