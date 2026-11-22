"""Task 26b item 3: a forwarded header changes the scheme or the rate-limit address only when a
trusted proxy count says a proxy wrote it. The two untrusted cases guard what already holds."""

from datetime import UTC, datetime

import pytest
from django.http import HttpRequest
from django.test import Client

from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.network_address import network_address

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SEARCHES_PER_HOUR = 120
PROXY_ADDRESS = "10.0.0.5"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _search_statuses(client: Client, forwarded: list[str]) -> list[int]:
    return [
        client.get(
            "/api/v1/search/providers", HTTP_X_FORWARDED_FOR=entry, REMOTE_ADDR=PROXY_ADDRESS
        ).status_code
        for entry in forwarded
    ]


def returns_http_scheme_when_forwarded_proto_comes_from_untrusted_caller(
    settings: object,
) -> None:
    settings.TRUSTED_PROXY_COUNT = 0  # type: ignore[attr-defined]
    settings.SECURE_PROXY_SSL_HEADER = None  # type: ignore[attr-defined]

    response = browser_api_client().get("/api/v1/health", HTTP_X_FORWARDED_PROTO="https")

    assert response.wsgi_request.is_secure() is False


def returns_remote_address_for_rate_limit_when_forwarded_for_comes_from_untrusted_caller(
    settings: object,
) -> None:
    settings.TRUSTED_PROXY_COUNT = 0  # type: ignore[attr-defined]
    forwarded = [f"203.0.113.{number}" for number in range(SEARCHES_PER_HOUR + 1)]

    statuses = _search_statuses(browser_api_client(), forwarded)

    assert statuses[SEARCHES_PER_HOUR] == 429


def returns_forwarded_address_counter_when_one_proxy_is_trusted(settings: object) -> None:
    settings.TRUSTED_PROXY_COUNT = 1  # type: ignore[attr-defined]
    client = browser_api_client()
    first_caller = _search_statuses(client, ["203.0.113.1"] * (SEARCHES_PER_HOUR + 1))

    second_caller = _search_statuses(client, ["203.0.113.2"])

    assert first_caller[SEARCHES_PER_HOUR] == 429
    assert second_caller == [200]


def returns_forwarded_address_when_one_proxy_is_trusted_and_header_is_set(settings: object) -> None:
    settings.TRUSTED_PROXY_COUNT = 1  # type: ignore[attr-defined]
    request = HttpRequest()
    request.META["REMOTE_ADDR"] = PROXY_ADDRESS
    request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.9, 203.0.113.4"

    assert network_address(request) == "203.0.113.4"
