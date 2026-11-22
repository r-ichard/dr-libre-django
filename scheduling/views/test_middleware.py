from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from scheduling.use_cases.request_context import current_request_context
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client


def returns_same_correlation_id_when_header_is_sane() -> None:
    response = browser_api_client().get("/api/v1/health", headers={"x-correlation-id": "req-42"})

    assert response["X-Correlation-Id"] == "req-42"


@pytest.mark.parametrize("bad", ["a" * 65, "has space", "semi;colon", "é"])
def returns_generated_id_when_header_is_too_long_or_has_bad_characters(bad: str) -> None:
    response = browser_api_client().get("/api/v1/health", headers={"x-correlation-id": bad})

    generated = response["X-Correlation-Id"]
    assert generated != bad
    assert 1 <= len(generated) <= 64


def returns_distinct_generated_ids_when_no_header_is_sent() -> None:
    first = browser_api_client().get("/api/v1/health")["X-Correlation-Id"]
    second = browser_api_client().get("/api/v1/health")["X-Correlation-Id"]

    assert first and first != second


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/unknown", "/api/v1/probe/explode"])
def returns_correlation_id_header_when_response_is_success_unknown_path_or_500(
    path: str, settings: object
) -> None:
    settings.ROOT_URLCONF = "scheduling.views.probe_urls"  # type: ignore[attr-defined]

    response = browser_api_client(raise_request_exception=False).get(
        path, headers={"x-correlation-id": "cid-9"}
    )

    assert response["X-Correlation-Id"] == "cid-9"


def returns_context_correlation_id_to_use_case_when_request_is_handled(
    probe_client: Client,
) -> None:
    response = probe_client.get("/api/v1/probe/context", headers={"x-correlation-id": "cid-7"})

    assert response.json()["correlation_id"] == "cid-7"


def returns_one_instant_when_context_is_read_twice_in_a_request(
    probe_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    instants = iter(datetime(2026, 5, 1, tzinfo=UTC) + timedelta(seconds=n) for n in range(100))
    monkeypatch.setattr(clock, "now_utc", lambda: next(instants))

    body = probe_client.get("/api/v1/probe/context").json()

    assert body["first"] == body["second"] == "2026-05-01T00:00:00+00:00"


def returns_patched_instant_when_clock_is_replaced(
    probe_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 2, 3, 4, tzinfo=UTC))

    body = probe_client.get("/api/v1/probe/context").json()

    assert body["first"] == "2030-01-02T03:04:00+00:00"


def raises_when_context_is_read_after_request_has_finished() -> None:
    browser_api_client().get("/api/v1/health")

    with pytest.raises(LookupError):
        current_request_context()


def returns_generic_json_500_with_correlation_id_when_plain_view_raises_on_api_path_under_debug(
    probe_client: Client, settings: object
) -> None:
    settings.DEBUG = True  # type: ignore[attr-defined]

    response = probe_client.get(
        "/api/v1/probe/plain-explode", headers={"x-correlation-id": "cid-x"}
    )

    assert response.status_code == 500
    error = response.json()["error"]
    assert (error["code"], error["message"], error["correlation_id"]) == (
        "internal_error",
        "Something went wrong.",
        "cid-x",
    )
    assert "patient reports chest pain" not in response.content.decode()


def returns_correlation_id_header_when_plain_view_raises_on_page_path(
    probe_client: Client,
) -> None:
    response = probe_client.get("/pages/explode", headers={"x-correlation-id": "cid-x"})

    assert response["X-Correlation-Id"] == "cid-x"
