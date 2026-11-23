"""Sections 12.3, 14 and 16: every page route has a row in the access table, and every row names
a route that exists. Rows sit in test_page_access_rows*.py; ADR 0012 holds the readings.
Coverage runs with DEBUG off; the DEBUG-on branch adds the `style` row."""

from collections.abc import Iterator

from django.conf import settings
from django.test import override_settings
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.views.pages.test_page_access_rows import NO_SESSION_ROWS, STYLE_ROWS, Row
from scheduling.views.pages.test_page_access_rows_admin import ADMIN_RECORD_ROWS
from scheduling.views.pages.test_page_access_rows_admin_operations import ADMIN_OPERATION_ROWS
from scheduling.views.pages.test_page_access_rows_clinician import CLINICIAN_ROWS
from scheduling.views.pages.test_page_access_rows_patient import PATIENT_ROWS

# The product's JSON API, its FHIR surface and the static files are not page routes.
NOT_PAGE_PREFIXES = ("api/", "fhir", "static/")


def _all_rows() -> list[Row]:
    return [
        *NO_SESSION_ROWS,
        *PATIENT_ROWS,
        *CLINICIAN_ROWS,
        *ADMIN_RECORD_ROWS,
        *ADMIN_OPERATION_ROWS,
        *STYLE_ROWS,
    ]


def _expected_routes() -> list[str]:
    return [row.route for row in _all_rows() if settings.DEBUG or not row.debug_only]


def _route_strings(patterns: list[URLPattern | URLResolver], prefix: str = "") -> Iterator[str]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _route_strings(list(entry.url_patterns), prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern)


def _page_routes() -> list[str]:
    configured = _route_strings(list(get_resolver().url_patterns))
    # Regex entries print with a leading "^"; the prefix test needs the bare path.
    pages = {route.removeprefix("^") for route in configured}
    return sorted(route for route in pages if not route.startswith(NOT_PAGE_PREFIXES))


def returns_no_failure_when_every_page_route_has_a_row() -> None:
    configured = _page_routes()
    expected = _expected_routes()
    missing_rows = sorted(set(configured) - set(expected))
    stale_rows = sorted(set(expected) - set(configured))
    assert missing_rows == [] and stale_rows == [], (
        f"missing_rows={missing_rows} stale_rows={stale_rows}"
    )


def returns_one_row_per_route_when_table_read() -> None:
    routes = [row.route for row in _all_rows()]
    duplicates = sorted({route for route in routes if routes.count(route) > 1})
    assert duplicates == [], f"duplicate_rows={duplicates}"


def returns_no_debug_row_expected_when_debug_is_off() -> None:
    debug_routes = {row.route for row in _all_rows() if row.debug_only}
    with override_settings(DEBUG=False):
        expected = set(_expected_routes())
    leaked = sorted(debug_routes & expected)
    assert leaked == [], f"debug_rows_expected={leaked}"


def returns_debug_row_expected_when_debug_is_on() -> None:
    with override_settings(DEBUG=True):
        expected = _expected_routes()
    assert "style" in expected, "style row not expected when DEBUG is on"
