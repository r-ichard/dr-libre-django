"""Task 26a2 item 1: a write without a body is never refused as unreadable, whatever its type says.
wsgiref fills CONTENT_TYPE with text/plain when the header is absent, so every write route of the
URL configuration is sent that way."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.views.api_clients import browser_api_client
from scheduling.views.api_view import ApiView, NotFoundView

pytestmark = pytest.mark.django_db

UNREADABLE = "The request body is not readable."
MADE_UP_UUID = "00000000-0000-4000-8000-000000000000"
WRITE_HANDLERS = ("post", "put", "patch", "delete")
KNOWN_WRITE_ROUTES = 15


def _api_views(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, type[ApiView]]]:
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _api_views(list(pattern.url_patterns), route)
            continue
        view_class = getattr(pattern.callback, "cls", None)
        if not (isinstance(view_class, type) and issubclass(view_class, ApiView)):
            continue
        if route.startswith("api/v1/") and view_class is not NotFoundView:
            yield route, view_class


def _write_requests() -> list[tuple[str, str]]:
    requests: list[tuple[str, str]] = []
    for route, view_class in _api_views(list(get_resolver().url_patterns)):
        path = "/" + re.sub(r"<uuid:\w+>", MADE_UP_UUID, route)
        requests.extend((method, path) for method in WRITE_HANDLERS if hasattr(view_class, method))
    return requests


def returns_the_known_write_routes_when_the_url_configuration_is_walked() -> None:
    assert len(_write_requests()) >= KNOWN_WRITE_ROUTES


@pytest.mark.parametrize(("method", "path"), _write_requests())
def returns_no_unreadable_body_refusal_when_any_api_write_route_gets_no_body_and_text_plain(
    method: str, path: str
) -> None:
    # The test client sets no type for an empty body, as wsgiref does: the environ is set directly.
    response = browser_api_client().generic(method, path, CONTENT_TYPE="text/plain")

    assert UNREADABLE not in response.content.decode()
