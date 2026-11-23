"""Section 12.3: a page without a record in its address gets its row's answer from each caller,
or the product's where a pair is listed. Record pages: test_page_access_records.py. Form-only
pages: test_page_access_form_walk.py."""

from collections.abc import Callable, Iterator
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.http.response import HttpResponseBase
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from django.views import View

from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.page_walk_support import World, client_for_role, make_world, path_of
from scheduling.views.pages.test_page_access_rows import (
    KNOWN_DIFFERENCES,
    Answer,
    Caller,
    Row,
)
from scheduling.views.pages.test_page_access_table import _all_rows

CALLERS: tuple[Caller, ...] = ("visitor", "patient", "clinician", "admin")

pytestmark = pytest.mark.django_db

# Routes that answer no GET. test_page_access_form_walk.py posts their forms. Their redirects
# (for example "302 /sign-in") are not SIGN_IN to _answer_of, so their pairs are compared as sent.
FORM_WALKED_ROUTES = frozenset(
    {
        "sign-out",
        "sign-in/email-link",
        "patient/notifications/read-all",
        "admin-console/appointments/export",
        "admin-console/settings/reminders",
    }
)

# The product's JSON API, its FHIR surface and the static files are not pages.
NOT_PAGE_PREFIXES = ("api/", "fhir", "static/")


def _answer_of(response: HttpResponseBase) -> str:
    if response.status_code == 200:
        return Answer.OK
    if response.status_code == 403:
        return Answer.FORBIDDEN
    if response.status_code == 404:
        return Answer.NOT_FOUND
    if response.status_code in (302, 303):
        location = response.headers.get("Location", "")
        if urlsplit(location).path.startswith("/sign-in"):
            return Answer.SIGN_IN
        return f"{response.status_code} {location}"
    return str(response.status_code)


def _expected_answer(row: Row, caller: Caller) -> Answer:
    match caller:
        case "visitor":
            return row.visitor
        case "patient":
            return row.patient
        case "clinician":
            return row.clinician
        case "admin":
            return row.admin


def _walked_rows() -> list[Row]:
    return [
        row
        for row in _all_rows()
        if not row.names_record
        and row.route not in FORM_WALKED_ROUTES
        and (settings.DEBUG or not row.debug_only)
    ]


def _clients(world: World) -> dict[Caller, Client]:
    return {
        "visitor": Client(),
        "patient": client_for_role("patient", world),
        "clinician": client_for_role("clinician", world),
        "admin": client_for_role("admin", world),
    }


def _wanted(row: Row, caller: Caller) -> str:
    if (row.route, caller) in KNOWN_DIFFERENCES:
        return KNOWN_DIFFERENCES[row.route, caller][1]
    return _expected_answer(row, caller)


def _url_callbacks(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, Callable[..., object]]]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _url_callbacks(list(entry.url_patterns), prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern), entry.callback


def _page_callbacks() -> dict[str, Callable[..., object]]:
    configured = _url_callbacks(list(get_resolver().url_patterns))
    # Regex entries print with a leading "^"; they are the API and FHIR routes, not pages.
    return {
        route: callback
        for route, callback in configured
        if not route.startswith("^") and not route.startswith(NOT_PAGE_PREFIXES)
    }


def _answers_get(callback: object) -> bool:
    view_class = getattr(callback, "view_class", None)
    # A function view, such as the favicon redirect, takes every method.
    if not isinstance(view_class, type) or not issubclass(view_class, View):
        return True
    if "get" not in view_class.http_method_names:
        return False
    return not (issubclass(view_class, PageView) and view_class().is_form_only)


def returns_every_get_route_in_walk_when_resolver_lists_it() -> None:
    record_routes = {row.route for row in _all_rows() if row.names_record}
    resolver_routes = {
        route
        for route, callback in _page_callbacks().items()
        if route not in record_routes and _answers_get(callback)
    }
    expected = resolver_routes - FORM_WALKED_ROUTES
    walked = {row.route for row in _walked_rows()}
    missing = sorted(expected - walked)
    extra = sorted(walked - expected)
    assert missing == [] and extra == [], f"missing_from_walk={missing} extra_in_walk={extra}"


def returns_row_answer_when_caller_gets_walked_page() -> None:
    world = make_world()
    clients = _clients(world)
    mismatches: list[str] = []
    for row in _walked_rows():
        for caller in CALLERS:
            want = _wanted(row, caller)
            got = _answer_of(clients[caller].get(path_of(row.route, world)))
            if got != want:
                mismatches.append(f"{caller} {row.route}: want {want} got {got}")
    assert mismatches == [], "\n".join(mismatches)


def returns_product_answer_when_pair_is_known_difference() -> None:
    world = make_world()
    clients = _clients(world)
    record_routes = {row.route for row in _all_rows() if row.names_record}
    mismatches: list[str] = []
    for (route, caller), (_, product_answer) in KNOWN_DIFFERENCES.items():
        # A record route's pair is checked on its own record by test_page_access_records.py. A
        # form route answers a GET with 405, so its pair is posted by test_page_access_form_walk.py.
        if route in record_routes or route in FORM_WALKED_ROUTES:
            continue
        got = _answer_of(clients[caller].get(path_of(route, world)))
        if got != product_answer:
            mismatches.append(f"{caller} {route}: want {product_answer} got {got}")
    assert mismatches == [], "\n".join(mismatches)


def returns_known_difference_only_when_answer_differs_from_row() -> None:
    rows = {row.route: row for row in _all_rows()}
    mismatches: list[str] = []
    for (route, caller), (table_answer, product_answer) in KNOWN_DIFFERENCES.items():
        if table_answer != _expected_answer(rows[route], caller) or table_answer == product_answer:
            mismatches.append(f"{caller} {route}: table {table_answer} product {product_answer}")
    assert mismatches == [], "\n".join(mismatches)
