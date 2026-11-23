"""Section 16: every page the product can render, signed out and as each role, meets the
accessibility floor of section 16. Routes come from the URL configuration, so a new page is
walked without anyone listing it."""

from __future__ import annotations

import pytest

from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW
from scheduling.views.pages.page_quality_findings import findings_of
from scheduling.views.pages.page_walk_support import (
    ROLES,
    client_for_role,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

MINIMUM_PAGES = 30


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_no_finding_when_any_page_is_walked_as_each_role() -> None:
    world = make_world()
    walked = 0
    problems: dict[str, list[str]] = {}

    for role in ROLES:
        client = client_for_role(role, world)
        for route in page_routes():
            response = client.get(path_of(route, world))
            if response.status_code != 200 or "text/html" not in response["Content-Type"]:
                continue
            walked += 1
            findings = findings_of(response.content.decode())
            if findings:
                problems[f"{role} {route}"] = findings

    assert walked > MINIMUM_PAGES
    assert problems == {}


def returns_a_finding_when_html_has_a_heading_jump_and_no_main() -> None:
    html = "<html lang='en'><title>x</title><h1>a</h1><h3>b</h3></html>"

    assert findings_of(html) == ["heading jumps from h1 to h3", "page without main"]


PAGE = "<html lang='en'><title>t</title><main><h1>a</h1>{body}</main></html>"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<input name='q'>", ["field without label: q"]),
        ("<label for='q'>Q</label><input id='q' name='q'>", []),
        ("<label>Q<input name='q'></label>", []),
        ("<img src='x'>", ["image without text alternative"]),
        ("<img src='x' alt=''>", []),
        ("<p id='a'></p><p id='a'></p>", ["duplicate id: a"]),
        ("<h1>b</h1>", ["2 h1 headings"]),
        ("<a href='/'></a>", ["a without a name"]),
        ("<a href='/'><span aria-hidden='true'>x</span></a>", ["a without a name"]),
        ("<a href='/'>Go</a>", []),
        ("<button></button>", ["button without a name"]),
        ("<table><tr><td>a</td></tr></table>", ["table without header cells"]),
        ("<table><tr><th>a</th></tr></table>", []),
    ],
)
def returns_exactly_the_expected_findings_when_html_has_one_known_problem(
    body: str, expected: list[str]
) -> None:
    assert findings_of(PAGE.format(body=body)) == expected


def returns_findings_for_a_missing_title_and_a_missing_lang() -> None:
    assert findings_of("<html lang='en'><main><h1>a</h1></main></html>") == ["page without a title"]
    assert findings_of("<html><title>t</title><main><h1>a</h1></main></html>") == [
        "page without lang"
    ]
