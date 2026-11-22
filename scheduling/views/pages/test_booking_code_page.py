"""Task 12a, code page: masked address, wrong code, expiry, resend."""

from __future__ import annotations

import re

import pytest
from django.core import mail

from scheduling.models import Appointment
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import (
    FORM,
    NOW,
    VISITOR_EMAIL,
    details_path,
    no_inline_code,
)
from scheduling.views.pages.browser_support import browser_client, browser_post

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _hold_page() -> tuple[object, str]:
    clinic = make_clinic()
    client = browser_client()
    location = browser_post(client, details_path(clinic), FORM)["Location"]
    return client, location


def returns_masked_email_ten_minutes_and_resend_button_when_code_page_opens() -> None:
    client, code_path = _hold_page()

    html = client.get(code_path).content.decode()  # type: ignore[attr-defined]

    assert "v***@example.test" in html
    assert VISITOR_EMAIL not in html
    assert "10 minutes" in html
    assert f'action="{code_path.replace("/code", "/resend")}"' in html
    assert no_inline_code(html)


def returns_303_to_confirmation_with_session_cookie_when_code_is_right() -> None:
    client, code_path = _hold_page()
    found = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert found is not None
    code = found.group(1)

    response = browser_post(client, code_path, {"code": code})  # type: ignore[arg-type]

    appointment = Appointment.objects.get()
    assert response.status_code == 303
    assert response["Location"] == f"/appointments/{appointment.pk}/confirmation"
    assert "drlibre_session" in response.cookies


def returns_message_with_tries_left_when_code_is_wrong() -> None:
    client, code_path = _hold_page()

    response = browser_post(client, code_path, {"code": "000000"})  # type: ignore[arg-type]

    assert response.status_code == 422
    assert "That code is not right. You have 4 tries left." in response.content.decode()


def returns_send_new_code_message_when_attempts_are_used_up() -> None:
    client, code_path = _hold_page()
    for _ in range(5):
        response = browser_post(client, code_path, {"code": "000000"})  # type: ignore[arg-type]

    assert "Send a new code to try again." in response.content.decode()


def returns_hold_expired_page_with_start_again_link_when_hold_is_unknown() -> None:
    client, _ = _hold_page()

    response = client.get("/book/holds/00000000-0000-4000-8000-000000000000/code")  # type: ignore[attr-defined]

    html = response.content.decode()
    assert response.status_code == 404
    assert "This booking has expired." in html
    assert 'href="/"' in html


def returns_sent_notice_after_resend() -> None:
    client, code_path = _hold_page()

    response = browser_post(client, code_path.replace("/code", "/resend"), {})  # type: ignore[arg-type]
    page = client.get(response["Location"])  # type: ignore[attr-defined]

    assert response.status_code == 303
    assert response["Location"] == f"{code_path}?sent=1"
    assert "We sent a new code." in page.content.decode()
    assert len(mail.outbox) == 2


def returns_singular_try_when_one_attempt_is_left() -> None:
    client, code_path = _hold_page()
    for _ in range(4):
        response = browser_post(client, code_path, {"code": "000000"})  # type: ignore[arg-type]

    assert "You have 1 try left." in response.content.decode()


MISSING_HOLD_PATH = "/book/holds/00000000-0000-4000-8000-000000000000/code"
HOLD_COOKIE = "drlibre_hold"


def _other_browser_page(path: str) -> object:
    return browser_client().get(path)


def returns_missing_hold_page_when_another_browser_opens_the_code_page() -> None:
    _, code_path = _hold_page()
    missing = browser_client().get(MISSING_HOLD_PATH)

    response = _other_browser_page(code_path)

    assert response.status_code == missing.status_code == 404  # type: ignore[attr-defined]
    assert "This booking has expired." in response.content.decode()  # type: ignore[attr-defined]
    assert "v***@example.test" not in response.content.decode()  # type: ignore[attr-defined]


def returns_missing_hold_page_and_no_booking_when_another_browser_posts_the_right_code() -> None:
    _, code_path = _hold_page()
    found = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert found is not None

    response = browser_post(browser_client(), code_path, {"code": found.group(1)})

    assert response.status_code == 404
    assert Appointment.objects.count() == 0


def returns_missing_hold_page_when_another_browser_asks_for_a_new_code() -> None:
    _, code_path = _hold_page()

    response = browser_post(browser_client(), code_path.replace("/code", "/resend"), {})

    assert response.status_code == 404
    assert len(mail.outbox) == 1


def returns_the_code_page_when_the_booking_browser_opens_it() -> None:
    client, code_path = _hold_page()

    response = client.get(code_path)  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert "v***@example.test" in response.content.decode()


def returns_http_only_strict_cookie_when_a_hold_is_made() -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), FORM)

    cookie = response.cookies[HOLD_COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"


def returns_missing_hold_page_when_the_cookie_of_another_hold_is_presented() -> None:
    first_client, first_path = _hold_page()
    second_client = browser_client()
    other_form = FORM | {"email": "other.visitor@example.test"}
    second_path = browser_post(second_client, details_path(make_clinic()), other_form)["Location"]
    assert second_client.get(second_path).status_code == 200
    assert first_client.get(first_path).status_code == 200  # type: ignore[attr-defined]

    response = second_client.get(first_path)

    assert response.status_code == 404
