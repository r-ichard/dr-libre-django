"""Section 7.1: the details form refuses a time that is not offered before it
shows, reports every error in one answer, applies the phone rule and keeps what was typed when
the time was taken meanwhile."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from scheduling.models import BookingHold
from scheduling.models.builders import STARTS_AT, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import FORM, NOW, details_path
from scheduling.views.pages.browser_support import browser_client, browser_post

pytestmark = pytest.mark.django_db

IN_THE_PAST = "2030-01-07T04:00:00Z"
OFF_THE_GRID = "2030-01-07T10:07:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _path_at(starts_at: str, clinic: object) -> str:
    base = details_path(clinic)  # type: ignore[arg-type]
    return re.sub(r"starts_at=[^&]+", f"starts_at={starts_at}", base)


@pytest.mark.parametrize("starts_at", [IN_THE_PAST, OFF_THE_GRID])
def returns_refusal_without_form_when_details_start_is_not_offered(starts_at: str) -> None:
    clinic = make_clinic()

    response = browser_client().get(_path_at(starts_at, clinic))

    html = response.content.decode()
    assert response.status_code >= 400
    assert 'id="id_full_name"' not in html


def returns_form_when_details_start_is_offered() -> None:
    clinic = make_clinic()

    response = browser_client().get(details_path(clinic))

    assert 'id="id_full_name"' in response.content.decode()


def returns_form_with_typed_values_when_the_slot_was_taken_meanwhile() -> None:
    clinic = make_clinic()
    make(
        "Appointment",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + timedelta(minutes=30),
    )

    response = browser_post(browser_client(), details_path(clinic), FORM)

    html = response.content.decode()
    assert response.status_code >= 400
    assert 'id="id_full_name"' in html
    assert 'value="Vera Visitor"' in html
    assert re.search(r'id="id_date_of_birth_year"[^>]*value="1985"', html)
    assert "just taken" in html
    assert BookingHold.objects.count() == 0


def returns_every_error_when_details_has_future_birth_date_bad_email_and_no_terms() -> None:
    clinic = make_clinic()
    form = {**FORM, "date_of_birth_year": "2030", "email": "notanemail", "phone": "abc"}
    form.pop("terms_accepted")

    response = browser_post(browser_client(), details_path(clinic), form)

    html = response.content.decode()
    assert response.status_code == 422
    for target in ["date_of_birth_day", "email", "phone", "terms_accepted"]:
        assert f'href="#id_{target}"' in html, target


@pytest.mark.parametrize("phone", ["abc", "12345", "1" * 21])
def returns_phone_error_when_details_phone_breaks_the_rule(phone: str) -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), {**FORM, "phone": phone})

    assert response.status_code == 422
    assert 'id="id_phone_error"' in response.content.decode()
    assert BookingHold.objects.count() == 0


def returns_303_when_details_phone_follows_the_rule() -> None:
    clinic = make_clinic()

    response = browser_post(
        browser_client(), details_path(clinic), {**FORM, "phone": "+49 (30) 123-456"}
    )

    assert response.status_code == 303
