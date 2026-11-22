"""Task 25d, item 1: a page title is plain text, no cross-site token sits outside a form, and
no two pages share a title. Each test states the behaviour in words."""

from __future__ import annotations

import re

import pytest

from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW
from scheduling.views.pages.page_quality_findings import TITLE_LIMIT, TOKEN_FIELD, findings_of
from scheduling.views.pages.page_walk_support import (
    ROLES,
    client_for_role,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

PAGE = "<html lang='en'><title>{title}</title><main><h1>a</h1>{body}</main></html>"
TOKEN_INPUT = f"<input type='hidden' name='{TOKEN_FIELD}' value='abc'>"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_a_finding_when_a_title_holds_markup() -> None:
    html = PAGE.format(title="A<form></form>", body="")

    assert findings_of(html) == ["title holds markup"]


def returns_a_finding_only_when_a_title_is_longer_than_80_characters() -> None:
    long_page = PAGE.format(title="x" * (TITLE_LIMIT + 1), body="")
    limit_page = PAGE.format(title="x" * TITLE_LIMIT, body="")

    assert findings_of(long_page) == ["title longer than 80 characters"]
    assert findings_of(limit_page) == []


def returns_a_finding_when_a_token_sits_outside_a_form() -> None:
    outside = PAGE.format(title="t", body=f"<p>{TOKEN_INPUT}</p>")
    inside = PAGE.format(title="t", body=f"<form method='post'>{TOKEN_INPUT}</form>")

    assert findings_of(outside) == ["cross-site token outside a form"]
    assert findings_of(inside) == []


def returns_the_admin_appointments_title_as_plain_text_when_the_page_opens() -> None:
    world = make_world()

    html = client_for_role("admin", world).get("/admin-console/appointments").content.decode()

    assert re.search(r"<title>Appointments · DrLibre</title>", html)
    assert html.count('action="/admin-console/appointments/export"') == 1
    assert html.index("<main") < html.index('action="/admin-console/appointments/export"')


def returns_no_two_pages_with_one_title_when_every_page_is_walked() -> None:
    world = make_world()
    paths_by_title: dict[tuple[str, str], set[str]] = {}

    for role in ROLES:
        client = client_for_role(role, world)
        for route in page_routes():
            path = path_of(route, world)
            response = client.get(path)
            if response.status_code != 200 or "text/html" not in response["Content-Type"]:
                continue
            found = re.search(r"<title>(.*?)</title>", response.content.decode(), re.S)
            title = found.group(1).strip() if found else ""
            paths_by_title.setdefault((role, title), set()).add(path)

    shared = {key: sorted(paths) for key, paths in paths_by_title.items() if len(paths) > 1}
    assert shared == {}
