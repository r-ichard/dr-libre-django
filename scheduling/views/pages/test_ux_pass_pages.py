"""Task 25: wording and order on the sign-in pages, the lockout window, the favicon, the waitlist
accept notice and the time grid's column width. Each test states the behaviour in words."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.test import Client

from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_post
from scheduling.views.pages.test_patient_waitlist_page import PATH, _offered
from scheduling.views.pages.test_screens_hardening import PHRASE, _make_user

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parents[3] / "static"
LINK_ACTION = 'action="/sign-in/email-link"'
PASSWORD_ACTION = 'action="/sign-in"'  # noqa: S105 - a form address, not a secret


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_the_email_form_before_the_password_form_when_signed_out_opens_sign_in() -> None:
    html = Client().get("/sign-in").content.decode()

    assert html.index(LINK_ACTION) < html.index(PASSWORD_ACTION)


def returns_no_false_claim_when_a_patient_with_a_password_reads_sign_in() -> None:
    html = Client().get("/sign-in").content.decode()

    assert "Clinicians and admins use a password" not in html
    assert "Patients can sign in with the email link. If you have a password, use it below." in html


@pytest.mark.parametrize("minutes", [5, 15])
def returns_the_link_lifetime_in_minutes_when_sign_in_is_opened(
    monkeypatch: pytest.MonkeyPatch, minutes: int
) -> None:
    monkeypatch.setattr(
        "scheduling.domain.sign_in_link_rules.LINK_LIFETIME", timedelta(minutes=minutes)
    )

    html = Client().get("/sign-in").content.decode()

    assert f"We send a link that works for {minutes} minutes and only once." in html


def returns_the_signed_in_name_when_the_link_not_valid_page_renders() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, "/sign-in/link", {"token": "not-a-real-token"})

    assert response.status_code == 400
    assert clinic.patient.full_name in response.content.decode()


def returns_the_window_in_minutes_when_the_lockout_window_is_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scheduling.domain.lockout_rules.LOCKOUT_WINDOW", timedelta(minutes=5))
    _make_user("PATIENT")
    for _ in range(10):
        Client().post("/sign-in", {"email": "jane@example.test", "password": "not the phrase"})

    response = Client().post("/sign-in", {"email": "jane@example.test", "password": PHRASE})

    assert "Try again in 5 minutes." in response.content.decode()


def returns_favicon_fill_equal_to_primary_token_when_the_files_are_read() -> None:
    tokens = (STATIC / "css" / "tokens.css").read_text()
    primary = re.search(r"--colour-primary:\s*(#[0-9a-fA-F]{6})", tokens)
    favicon = (STATIC / "favicon.svg").read_text()

    assert primary is not None
    assert f'rx="6" fill="{primary.group(1)}"' in favicon


def returns_a_notice_when_a_waitlist_offer_is_accepted() -> None:
    clinic = make_clinic()
    entry = _offered(clinic)
    client = signed_in_patient(clinic.patient)

    browser_post(client, f"{PATH}/{entry.pk}/accept", {})

    html = client.get("/patient/appointments").content.decode()
    assert "Your waitlist slot is booked." in html
