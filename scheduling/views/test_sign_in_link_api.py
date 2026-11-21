"""Section 14: POST /auth/link and POST /auth/link/verify. Same answer for every address."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.test import Client

from scheduling.models import AuditLogEntry, SignInLink
from scheduling.models.builders import make
from scheduling.views import clock

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db


def _wait_until_idle() -> None:
    """Imported here, so a module not written yet fails its tests and not the collection."""
    from scheduling.use_cases.background_mail import wait_until_idle  # noqa: PLC0415

    wait_until_idle()


ASK = "/api/v1/auth/link"
VERIFY = "/api/v1/auth/link/verify"
COOKIE = "drlibre_session"
EMAIL = "pat.link@example.test"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
MESSAGE = "This sign-in link has expired or was already used."


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _ask(email: str = EMAIL, client: Client | None = None) -> _MonkeyPatchedWSGIResponse:
    return (client or Client()).post(ASK, {"email": email}, content_type="application/json")


def _verify(token: str, client: Client | None = None) -> _MonkeyPatchedWSGIResponse:
    return (client or Client()).post(VERIFY, {"token": token}, content_type="application/json")


def _mailed_token() -> str:
    found = re.search(r"token=([A-Za-z0-9_-]+)", str(mail.outbox[-1].body))
    assert found is not None
    return found.group(1)


def _ask_and_deliver(
    django_capture_on_commit_callbacks: object, email: str = EMAIL
) -> _MonkeyPatchedWSGIResponse:
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        response = _ask(email)
    _wait_until_idle()
    return response


def returns_202_with_same_empty_body_when_email_is_patient_or_stranger(
    django_capture_on_commit_callbacks: object,
) -> None:
    make("User", email=EMAIL)

    patient = _ask_and_deliver(django_capture_on_commit_callbacks)
    stranger = _ask_and_deliver(django_capture_on_commit_callbacks, "nobody@example.test")

    assert (patient.status_code, stranger.status_code) == (202, 202)
    assert patient.json() == stranger.json() == {}
    assert patient.cookies.keys() == stranger.cookies.keys() == set()
    assert [message.to for message in mail.outbox] == [[EMAIL]]


@pytest.mark.parametrize("role", ["ADMIN", "CLINICIAN"])
def returns_202_and_no_mail_when_email_belongs_to_staff(
    django_capture_on_commit_callbacks: object, role: str
) -> None:
    make("User", email=EMAIL, role=role)

    response = _ask_and_deliver(django_capture_on_commit_callbacks)

    assert (response.status_code, response.json()) == (202, {})
    assert (len(mail.outbox), SignInLink.objects.count()) == (0, 0)


@pytest.mark.parametrize("body", [{"email": "not-an-email"}, {}, {"email": EMAIL, "role": "ADMIN"}])
def returns_400_invalid_input_when_body_is_malformed_or_has_unknown_field(
    body: dict[str, object],
) -> None:
    response = Client().post(ASK, body, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
    assert AuditLogEntry.objects.count() == 0


def returns_429_rate_limited_when_fourth_link_of_an_email_is_asked() -> None:
    make("User", email=EMAIL)
    for _ in range(3):
        assert _ask().status_code == 202

    response = _ask()

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def returns_202_when_mail_server_is_down(settings: object) -> None:
    make("User", email=EMAIL)
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {
            "BACKEND": "scheduling.use_cases.test_sign_in_link_support.MailServerDownBackend",
            "OPTIONS": {},
        }
    }

    response = _ask()

    assert (response.status_code, response.json()) == (202, {})


def returns_200_home_and_24_hour_cookie_when_verify_gets_the_mailed_token(
    django_capture_on_commit_callbacks: object,
) -> None:
    make("User", email=EMAIL)
    _ask_and_deliver(django_capture_on_commit_callbacks)

    response = _verify(_mailed_token())

    assert response.status_code == 200
    assert response.json() == {"home": "patient_portal"}
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["expires"] == "Tue, 08 Jan 2030 06:00:00 GMT"


@pytest.mark.parametrize("token", ["never-sent", "x" * 43])
def returns_400_with_the_one_message_when_token_is_unknown(token: str) -> None:
    response = _verify(token)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["details"]["fields"] == [{"field": "token", "message": MESSAGE}]
    assert COOKIE not in response.cookies


def returns_400_when_token_is_used_a_second_time(
    django_capture_on_commit_callbacks: object,
) -> None:
    make("User", email=EMAIL)
    _ask_and_deliver(django_capture_on_commit_callbacks)
    token = _mailed_token()
    assert _verify(token).status_code == 200

    assert _verify(token).status_code == 400


def returns_400_invalid_input_when_verify_body_is_malformed() -> None:
    response = Client().post(VERIFY, {"token": 5}, content_type="application/json")

    assert response.status_code == 400
