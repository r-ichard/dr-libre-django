"""Task 26a (#47): an answer that depends on who asks is never stored and says what it varies on."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth.hashers import make_password

from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client, fhir_client

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
PHRASE = "correct horse battery staple"
EMAIL = "cache.patient@example.test"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _signed_in_client() -> object:
    make("User", email=EMAIL, role="PATIENT", password=make_password(PHRASE))
    client = browser_api_client()
    response = client.post(
        "/api/v1/auth/login", {"email": EMAIL, "password": PHRASE}, content_type="application/json"
    )
    assert response.status_code == 200  # noqa: S101 - a failed sign-in is a broken test setup
    return client


def returns_no_store_and_vary_cookie_when_signed_in_caller_reads_api() -> None:
    client = _signed_in_client()

    response = client.get("/api/v1/appointments")  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert "Cookie" in response["Vary"]


def returns_vary_cookie_without_no_store_when_visitor_reads_public_search() -> None:
    response = browser_api_client().get("/api/v1/search/hospitals")

    assert response.status_code == 200
    assert "Cookie" in response["Vary"]
    assert "no-store" not in response.get("Cache-Control", "")


def returns_vary_cookie_when_caller_without_session_is_refused() -> None:
    response = browser_api_client().get("/api/v1/appointments")

    assert response.status_code == 401
    assert "Cookie" in response["Vary"]


def returns_no_store_when_caller_presents_a_bearer_token_without_cookie() -> None:
    response = fhir_client("dlk_unknown").get("/api/v1/appointments")

    assert response.status_code == 401
    assert response["Cache-Control"] == "no-store"
    assert "Authorization" in response["Vary"]
