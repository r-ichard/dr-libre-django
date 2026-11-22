"""Section 14 login and logout, section 12.3 origin rule. Cookie flags and the failure contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.models import AuditLogEntry, Session
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
COOKIE = "drlibre_session"
RIGHT_PHRASE = "correct horse battery staple"
EMAIL = "jane@example.test"
START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
FOREIGN_ORIGIN = "https://evil.example"
OWN_ORIGIN = "http://testserver"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: START)


def _make_user(role: str = "PATIENT") -> None:
    make("User", email=EMAIL, role=role, password=make_password(RIGHT_PHRASE))


def _login(
    client: Client, password: str = RIGHT_PHRASE, origin: str = ""
) -> _MonkeyPatchedWSGIResponse:
    headers = {"Origin": origin} if origin else {}
    return client.post(
        LOGIN,
        {"email": EMAIL, "password": password},
        content_type="application/json",
        headers=headers,
    )


def returns_200_home_and_cookie_when_login_is_right() -> None:
    _make_user("CLINICIAN")

    response = _login(browser_api_client())

    assert response.status_code == 200
    assert response.json() == {"home": "clinician_workspace"}
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert not cookie["secure"]
    assert len(cookie.value) >= 43


def returns_secure_cookie_when_https_only_is_on(settings: object) -> None:
    settings.HTTPS_ONLY = True  # type: ignore[attr-defined]
    _make_user()

    response = _login(browser_api_client())

    assert response.cookies[COOKIE]["secure"] is True


def returns_401_unauthenticated_with_equal_body_when_login_is_wrong_or_unknown() -> None:
    _make_user()
    client = browser_api_client()

    wrong = _login(client, "wrong password")
    unknown = client.post(
        LOGIN,
        {"email": "nobody@example.test", "password": RIGHT_PHRASE},
        content_type="application/json",
    )

    assert wrong.status_code == unknown.status_code == 401
    error = wrong.json()["error"]
    assert error["code"] == "unauthenticated"
    assert error["details"] == unknown.json()["error"]["details"]
    assert COOKIE not in wrong.cookies


@pytest.mark.parametrize(
    "body",
    [
        {"email": EMAIL, "password": RIGHT_PHRASE, "user_id": "someone-else"},
        {"email": "not-an-address", "password": RIGHT_PHRASE},
        {"email": EMAIL},
        {"email": EMAIL, "password": ""},
        {"email": EMAIL, "password": "x" * 1001},
    ],
)
def returns_400_invalid_input_when_login_body_breaks_the_schema(body: dict[str, str]) -> None:
    response = browser_api_client().post(LOGIN, body, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
    assert Session.objects.count() == 0


def returns_204_and_clears_cookie_when_logout_has_session() -> None:
    _make_user()
    client = browser_api_client()
    _login(client)

    response = client.post(LOGOUT, {}, content_type="application/json")

    assert response.status_code == 204
    assert response.cookies[COOKIE].value == ""
    assert Session.objects.count() == 0
    assert AuditLogEntry.objects.filter(action="auth.logout").count() == 1


def returns_204_when_logout_has_no_session() -> None:
    response = browser_api_client().post(LOGOUT, {}, content_type="application/json")

    assert response.status_code == 204
    assert AuditLogEntry.objects.filter(action="auth.logout").count() == 0


def returns_403_forbidden_when_login_post_has_foreign_origin() -> None:
    _make_user()

    response = _login(browser_api_client(), origin=FOREIGN_ORIGIN)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert Session.objects.count() == 0


def returns_403_when_post_has_origin_null() -> None:
    _make_user()

    response = _login(browser_api_client(), origin="null")

    assert response.status_code == 403


def returns_403_and_keeps_session_when_logout_post_has_foreign_origin() -> None:
    _make_user()
    client = browser_api_client()
    _login(client)

    response = client.post(LOGOUT, {}, content_type="application/json", HTTP_ORIGIN=FOREIGN_ORIGIN)

    assert response.status_code == 403
    assert Session.objects.count() == 1


def returns_204_when_logout_post_has_own_origin() -> None:
    _make_user()
    client = browser_api_client()
    _login(client)

    response = client.post(LOGOUT, {}, content_type="application/json", HTTP_ORIGIN=OWN_ORIGIN)

    assert response.status_code == 204


def returns_204_when_logout_post_has_no_origin() -> None:
    _make_user()
    client = browser_api_client()
    _login(client)

    assert client.post(LOGOUT, {}, content_type="application/json").status_code == 204


def returns_200_when_get_has_foreign_origin() -> None:
    response = browser_api_client().get("/api/v1/health", HTTP_ORIGIN=FOREIGN_ORIGIN)

    assert response.status_code == 200
