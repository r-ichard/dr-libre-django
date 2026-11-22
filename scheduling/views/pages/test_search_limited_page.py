"""Task 26a2 items 3 and 4: a limited visitor gets the search page itself with status 429, every
way on it answers, and every 429 says in seconds when to come back."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

import pytest
from django.test import Client

from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SEARCHES_PER_HOUR = 120
TEN_MINUTES = timedelta(minutes=10)
FIFTY_MINUTES_IN_SECONDS = "3000"


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    instant = [NOW]
    monkeypatch.setattr(clock, "now_utc", lambda: instant[0])
    return instant


def _limited_client() -> Client:
    client = browser_api_client()
    for _ in range(SEARCHES_PER_HOUR):
        assert client.get("/api/v1/search/providers").status_code == 200  # noqa: S101 - setup
    return client


class _Targets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.forms: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "form":
            self.forms.append(values.get("action") or "")


def _own_targets(html: str) -> _Targets:
    targets = _Targets()
    targets.feed(html)
    targets.links = [
        link for link in targets.links if link.startswith("/") and "static" not in link
    ]
    return targets


@pytest.mark.parametrize("path", ["/", "/?q=heart"])
def returns_search_page_with_429_and_form_when_address_is_limited(
    frozen_clock: list[datetime], path: str
) -> None:
    client = _limited_client()

    response = client.get(path)

    html = response.content.decode()
    assert response.status_code == 429
    assert "<header" in html
    assert 'name="q"' in html
    assert "<footer" in html
    assert "Sign in" in html


@pytest.mark.parametrize("path", ["/", "/?q=heart"])
def returns_below_400_for_every_link_on_the_limited_page(
    frozen_clock: list[datetime], path: str
) -> None:
    client = _limited_client()
    targets = _own_targets(client.get(path).content.decode())

    statuses = {link: client.get(link).status_code for link in targets.links}

    assert targets.links
    assert {link: status for link, status in statuses.items() if status >= 400} == {}


def returns_retry_after_and_sentence_that_agree_when_the_page_search_is_limited(
    frozen_clock: list[datetime],
) -> None:
    client = _limited_client()
    frozen_clock[0] = NOW + TEN_MINUTES

    response = client.get("/?q=heart")

    assert response.status_code == 429
    assert response["Retry-After"] == FIFTY_MINUTES_IN_SECONDS
    assert "Try again in 50 minutes." in response.content.decode()


def returns_retry_after_when_the_api_search_is_limited(frozen_clock: list[datetime]) -> None:
    client = _limited_client()
    frozen_clock[0] = NOW + TEN_MINUTES

    response = client.get("/api/v1/search/providers")

    assert response.status_code == 429
    assert response["Retry-After"] == FIFTY_MINUTES_IN_SECONDS


def returns_retry_after_when_the_bearer_token_is_limited(frozen_clock: list[datetime]) -> None:
    client = Client(headers={"Authorization": "Bearer dlk_wrong"})
    statuses = [client.get("/fhir/Patient").status_code for _ in range(7)]
    frozen_clock[0] = NOW + TEN_MINUTES

    response = client.get("/fhir/Patient")

    assert 429 in statuses
    assert response.status_code == 429
    assert re.fullmatch(r"\d+", response["Retry-After"])
    assert int(response["Retry-After"]) == 3000
