"""Section 7.3 pages: the sign-in page offers the link, the link opens a page with a button and
uses nothing, the button uses it."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from django.core import mail
from django.test import Client

from scheduling.models import Session, SignInLink, User
from scheduling.models.builders import make
from scheduling.use_cases.session import hash_token
from scheduling.views import clock

pytestmark = pytest.mark.django_db

SIGN_IN = "/sign-in"
ASK = "/sign-in/email-link"
CHECK_EMAIL = "/sign-in/check-email"
LINK = "/sign-in/link"
EMAIL = "pat.pages@example.test"
TOKEN = "planted-token-abcdefghijklmnopqrstuvwxyz"  # noqa: S105 - a planted test value
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
MESSAGE = "This sign-in link has expired or was already used."


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _stored_link(**overrides: object) -> SignInLink:
    patient = make("User", email=EMAIL)
    fields: dict[str, object] = {
        "token_hash": hash_token(TOKEN),
        "patient": patient,
        "created_at": NOW,
        "expires_at": datetime(2030, 1, 7, 6, 15, tzinfo=UTC),
    }
    link = make("SignInLink", **{**fields, **overrides})
    assert isinstance(link, SignInLink)
    return link


def returns_email_link_form_beside_the_password_form_when_sign_in_is_requested() -> None:
    html = Client().get(SIGN_IN).content.decode()

    assert "Email me a sign-in link" in html
    assert re.search(
        r'<form[^>]*action="/sign-in/email-link"[^>]*method="post"', html
    ) or re.search(r'<form[^>]*method="post"[^>]*action="/sign-in/email-link"', html)
    assert re.search(r'<input[^>]*id="id_link_email"', html)
    assert re.search(r'<label[^>]*for="id_link_email"', html)
    assert re.search(r'<form[^>]*action="/sign-in"', html)


@pytest.mark.parametrize("path", [SIGN_IN, CHECK_EMAIL, LINK])
def returns_no_inline_script_or_style_when_a_link_page_is_rendered(path: str) -> None:
    html = Client().get(f"{path}?token={TOKEN}" if path == LINK else path).content.decode()

    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "style=" not in html
    assert "<style" not in html


def returns_303_to_check_your_email_page_for_patient_and_stranger_alike(
    django_capture_on_commit_callbacks: object,
) -> None:
    make("User", email=EMAIL)

    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        patient = Client().post(ASK, {"link_email": EMAIL})
        stranger = Client().post(ASK, {"link_email": "nobody@example.test"})

    assert (patient.status_code, stranger.status_code) == (303, 303)
    assert patient["Location"] == stranger["Location"] == CHECK_EMAIL


def returns_check_your_email_page_without_the_address_when_it_is_opened() -> None:
    response = Client().get(CHECK_EMAIL)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Check your email" in html
    assert re.search(r"<h1[^>]*>\s*Check your email", html)


def returns_form_with_message_and_400_when_link_email_is_empty() -> None:
    response = Client().post(ASK, {"link_email": ""})

    assert response.status_code == 400
    assert "Enter your email address." in response.content.decode()


def returns_form_with_message_and_429_when_fourth_link_of_an_email_is_asked() -> None:
    for _ in range(3):
        assert Client().post(ASK, {"link_email": EMAIL}).status_code == 303

    response = Client().post(ASK, {"link_email": EMAIL})

    assert response.status_code == 429
    assert "Email me a sign-in link" in response.content.decode()


def returns_continue_button_and_uses_nothing_when_link_page_is_opened() -> None:
    link = _stored_link()

    response = Client().get(f"{LINK}?token={TOKEN}")

    html = response.content.decode()
    assert response.status_code == 200
    assert re.search(r"<button[^>]*>\s*Continue\s*</button>", html)
    assert re.search(r'<form[^>]*method="post"', html)
    link.refresh_from_db()
    assert link.used_at is None
    assert Session.objects.count() == 0
    assert "drlibre_session" not in response.cookies


def returns_same_page_when_link_page_is_opened_with_unknown_token() -> None:
    _stored_link()

    known = Client().get(f"{LINK}?token={TOKEN}")
    unknown = Client().get(f"{LINK}?token=never-sent-token")

    assert known.status_code == unknown.status_code == 200
    assert "Continue" in unknown.content.decode()


def returns_origin_only_referrer_policy_when_link_page_is_opened() -> None:
    response = Client().get(f"{LINK}?token={TOKEN}")

    assert response["Referrer-Policy"] == "strict-origin"


def returns_origin_only_referrer_policy_when_link_cannot_be_used() -> None:
    response = Client().post(LINK, {"token": "never-sent-token"})

    assert (response.status_code, response["Referrer-Policy"]) == (400, "strict-origin")


def returns_origin_only_referrer_policy_when_button_is_pressed() -> None:
    _stored_link()

    response = Client().post(LINK, {"token": TOKEN})

    assert (response.status_code, response["Referrer-Policy"]) == (303, "strict-origin")


def returns_303_to_patient_home_without_token_and_cookie_when_button_is_pressed() -> None:
    _stored_link()

    response = Client().post(LINK, {"token": TOKEN})

    assert response.status_code == 303
    assert response["Location"] == "/patient/"
    assert TOKEN not in response["Location"]
    assert response.cookies["drlibre_session"]["httponly"] is True
    assert SignInLink.objects.get().used_at == NOW
    assert Session.objects.get().opened_by == "EMAIL_LINK"


def returns_patient_home_when_the_session_of_a_used_link_is_followed() -> None:
    _stored_link()
    client = Client()
    client.post(LINK, {"token": TOKEN})

    assert client.get("/patient/").status_code == 200


@pytest.mark.parametrize("state", [{"used_at": NOW}, {"cancelled_at": NOW}])
def returns_one_message_and_offer_of_a_new_link_when_link_cannot_be_used(
    state: dict[str, object],
) -> None:
    _stored_link(**state)

    response = Client().post(LINK, {"token": TOKEN})

    html = response.content.decode()
    assert response.status_code == 400
    assert MESSAGE in html
    assert re.search(r'<a[^>]*href="/sign-in"[^>]*>\s*Email me a new sign-in link', html)
    assert TOKEN not in html
    assert Session.objects.count() == 0


def returns_same_page_when_token_is_unknown_or_missing() -> None:
    unknown = Client().post(LINK, {"token": "never-sent-token"})
    missing = Client().post(LINK, {})

    assert (unknown.status_code, missing.status_code) == (400, 400)
    assert MESSAGE in unknown.content.decode()
    assert MESSAGE in missing.content.decode()


def returns_403_when_button_is_pressed_without_csrf_token() -> None:
    _stored_link()

    response = Client(enforce_csrf_checks=True).post(LINK, {"token": TOKEN})

    assert response.status_code == 403
    assert SignInLink.objects.get().used_at is None


def returns_mail_with_link_to_the_continue_page_when_a_patient_asks(
    django_capture_on_commit_callbacks: object,
) -> None:
    make("User", email=EMAIL)

    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        Client().post(ASK, {"link_email": EMAIL})
    from scheduling.use_cases.background_mail import wait_until_idle  # noqa: PLC0415

    wait_until_idle()

    assert re.search(
        r"http://127\.0\.0\.1:8000/sign-in/link\?token=[\w-]{43}", str(mail.outbox[0].body)
    )
    assert User.objects.count() == 1
