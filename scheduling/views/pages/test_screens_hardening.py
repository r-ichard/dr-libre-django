"""Sections 12, 16: cookie renewal, favicon, lockout wording, CSRF cookie, table region."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.contrib.auth.hashers import make_password
from django.template.loader import render_to_string
from django.test import Client
from django.utils.http import http_date

from scheduling.models.builders import make
from scheduling.views import clock

pytestmark = pytest.mark.django_db

COOKIE = "drlibre_session"
PHRASE = "correct horse battery staple"
START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
ADMIN_HOME = "/admin-console/"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: START)


def _move_clock(monkeypatch: pytest.MonkeyPatch, later: timedelta) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: START + later)


def _make_user(role: str, email: str = "jane@example.test") -> None:
    make("User", email=email, role=role, full_name="Jane Doe", password=make_password(PHRASE))


def _signed_in_client(role: str) -> Client:
    _make_user(role)
    client = Client()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "jane@example.test", "password": PHRASE},
        content_type="application/json",
    )
    assert login.status_code == 200
    return client


def returns_renewed_session_cookie_when_page_request_comes_after_half_the_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _signed_in_client("ADMIN")
    _move_clock(monkeypatch, timedelta(hours=7))

    response = client.get(ADMIN_HOME)

    expected_expiry = http_date((START + timedelta(hours=19)).timestamp())
    assert response.cookies[COOKIE]["expires"] == expected_expiry


def returns_no_session_cookie_when_page_request_comes_before_half_the_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _signed_in_client("ADMIN")
    _move_clock(monkeypatch, timedelta(hours=1))

    response = client.get(ADMIN_HOME)

    assert COOKIE not in response.cookies


def returns_renewed_cookie_on_forbidden_page(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _signed_in_client("PATIENT")
    _move_clock(monkeypatch, timedelta(days=4))

    response = client.get(ADMIN_HOME)

    expected_expiry = http_date((START + timedelta(days=11)).timestamp())
    assert response.status_code == 403
    assert response.cookies[COOKIE]["expires"] == expected_expiry


def returns_new_session_cookie_when_signed_in_user_past_half_life_posts_other_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _signed_in_client("ADMIN")
    old_token = client.cookies[COOKIE].value
    make(
        "User",
        email="other@example.test",
        role="CLINICIAN",
        full_name="Other Doc",
        password=make_password(PHRASE),
    )
    _move_clock(monkeypatch, timedelta(hours=7))

    client.post("/sign-in", {"email": "other@example.test", "password": PHRASE})

    assert client.cookies[COOKIE].value != old_token


def returns_icon_when_favicon_is_requested() -> None:
    client = Client()

    redirect = client.get("/favicon.ico")
    icon = client.get("/static/favicon.svg")
    icon.close()
    page = client.get("/sign-in").content.decode()

    assert redirect.status_code == 302
    assert redirect["Location"] == "/static/favicon.svg"
    assert icon.status_code == 200
    assert icon["Content-Type"].startswith("image/svg+xml")
    assert 'rel="icon"' in page


def returns_lockout_message_with_wait_stated_once_when_account_is_locked_out() -> None:
    _make_user("PATIENT")
    for _ in range(10):
        client = Client()
        client.post("/sign-in", {"email": "jane@example.test", "password": "not the phrase"})

    response = client.post("/sign-in", {"email": "jane@example.test", "password": PHRASE})

    html = response.content.decode()
    assert "Try again in 15 minutes." in html
    assert "later" not in html


def returns_httponly_csrf_cookie_when_sign_in_form_is_requested() -> None:
    response = Client().get("/sign-in")

    assert response.cookies["csrftoken"]["httponly"] is True


class _TableWrapFinder(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.attributes: dict[str, str | None] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if "table-wrap" in (found.get("class") or "").split():
            self.attributes = found


def returns_focusable_labelled_region_when_table_is_wider_than_its_wrapper() -> None:
    finder = _TableWrapFinder()

    finder.feed(render_to_string("style.html"))

    assert finder.attributes is not None
    assert finder.attributes.get("tabindex") == "0"
    assert finder.attributes.get("role") == "region"
    assert finder.attributes.get("aria-label")


STYLESHEET_DIRECTORY = Path(__file__).resolve().parents[3] / "static" / "css"


def returns_shared_edge_rule_when_header_and_footer_are_styled() -> None:
    base = (STYLESHEET_DIRECTORY / "base.css").read_text()
    assert "--page-edge" in base
    assert base.count("var(--page-edge)") == 2


def returns_zero_top_margin_when_card_heading_comes_first() -> None:
    components = (STYLESHEET_DIRECTORY / "components.css").read_text()
    assert ".card > :first-child { margin-top: 0; }" in components
