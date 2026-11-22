"""Task 26a (#48): a write to /api/v1 takes JSON only; any other media type is refused before the
body is read, since a browser sends text/plain across sites without a preflight."""

from datetime import UTC, datetime

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.models import Session
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
PHRASE = "correct horse battery staple"
EMAIL = "type.patient@example.test"
UNREADABLE = "The request body is not readable."
LOGIN = "/api/v1/auth/login"
BODY = f'{{"email": "{EMAIL}", "password": "{PHRASE}"}}'


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.fixture
def patient() -> None:
    make("User", email=EMAIL, role="PATIENT", password=make_password(PHRASE))


def _signed_in(client: Client) -> Client:
    response = client.post(LOGIN, BODY, content_type="application/json")
    assert response.status_code == 200  # noqa: S101 - a failed sign-in is a broken test setup
    return client


@pytest.mark.parametrize("media_type", ["text/plain", "application/x-www-form-urlencoded"])
def returns_invalid_input_when_login_body_is_not_json(patient: None, media_type: str) -> None:
    response = browser_api_client().post(LOGIN, BODY, content_type=media_type)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"


def returns_invalid_input_when_cookie_authenticated_write_is_text_plain(patient: None) -> None:
    client = _signed_in(browser_api_client())

    response = client.post("/api/v1/auth/logout", BODY, content_type="text/plain")

    assert response.status_code == 400
    assert UNREADABLE in str(response.json()["error"]["details"])
    assert Session.objects.count() == 1


def returns_no_unreadable_refusal_when_text_plain_write_has_an_empty_content_length(
    patient: None,
) -> None:
    response = browser_api_client().generic(
        "POST", LOGIN, BODY, content_type="text/plain", CONTENT_LENGTH=""
    )

    assert UNREADABLE not in str(response.json())


def returns_unchanged_answer_when_write_body_is_json_with_charset(patient: None) -> None:
    response = browser_api_client().post(
        LOGIN, BODY, content_type="application/json; charset=utf-8"
    )

    assert response.status_code == 200


def returns_success_when_write_has_no_body(patient: None) -> None:
    client = _signed_in(browser_api_client())

    response = client.generic("POST", "/api/v1/auth/logout")

    assert response.status_code == 204


def returns_refusal_before_the_body_is_read_when_write_is_text_plain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_read(_request: object) -> None:
        raise AssertionError("body read before the media type was checked")

    monkeypatch.setattr("scheduling.views.api_view.refuse_oversized", fail_if_read)

    response = browser_api_client(raise_request_exception=False).post(
        LOGIN, BODY, content_type="text/plain"
    )

    assert response.status_code == 400


def returns_invalid_input_when_write_has_a_body_and_no_content_type(patient: None) -> None:
    response = browser_api_client().generic("POST", LOGIN, BODY, content_type="")

    assert response.status_code == 400
    assert UNREADABLE in str(response.json()["error"]["details"])
