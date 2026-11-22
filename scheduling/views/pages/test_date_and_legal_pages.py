"""Task 25b: terms and privacy pages, the date of birth as three fields, as a browser sends them."""

from __future__ import annotations

import re
from datetime import date

import pytest

from scheduling.models import BookingHold, User
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import (
    FORM,
    NOW,
    details_path,
    no_inline_code,
    signed_in_patient,
)
from scheduling.views.pages.browser_support import browser_client, browser_post

pytestmark = pytest.mark.django_db

PARTS = {"date_of_birth_day": "14", "date_of_birth_month": "3", "date_of_birth_year": "1985"}
PROFILE = "/patient/profile"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _patient(**fields: object) -> User:
    patient = make("User", **fields)
    assert isinstance(patient, User)
    return patient


def _details_form(**overrides: str) -> dict[str, str]:
    without_iso = {key: value for key, value in FORM.items() if key != "date_of_birth"}
    return {**without_iso, **PARTS, **overrides}


@pytest.mark.parametrize("path", ["/terms", "/privacy"])
def returns_200_placeholder_text_signed_out_when_legal_page_is_opened(path: str) -> None:
    response = browser_client().get(path)

    assert response.status_code == 200
    assert "placeholder text" in response.content.decode()
    assert "The hospital must supply its own" in response.content.decode()


@pytest.mark.parametrize("path", ["/sign-in", "/terms", "/privacy"])
def returns_footer_links_to_terms_and_privacy_when_any_page_is_opened(path: str) -> None:
    html = browser_client().get(path).content.decode()

    assert re.search(r'<footer.*<a[^>]*href="/terms".*<a[^>]*href="/privacy"', html, re.S)


def returns_links_to_terms_and_privacy_in_a_new_tab_when_details_page_is_rendered() -> None:
    html = browser_client().get(details_path(make_clinic())).content.decode()

    assert re.search(r'<a[^>]*href="/terms"[^>]*target="_blank"[^>]*rel="noopener"', html)
    assert re.search(r'<a[^>]*href="/privacy"[^>]*target="_blank"[^>]*rel="noopener"', html)
    assert "opens in a new tab" in html


def returns_three_labelled_inputs_in_one_fieldset_when_details_page_is_rendered() -> None:
    html = browser_client().get(details_path(make_clinic())).content.decode()

    assert html.count("<legend") == 1
    assert 'type="date"' not in html
    for part, autocomplete in [("day", "bday-day"), ("month", "bday-month"), ("year", "bday-year")]:
        tag = re.search(rf'<input[^>]*id="id_date_of_birth_{part}"[^>]*>', html)
        assert tag is not None, part
        assert 'inputmode="numeric"' in tag.group(0)
        assert f'autocomplete="{autocomplete}"' in tag.group(0)
        assert re.search(rf'<label[^>]*for="id_date_of_birth_{part}"', html)
    assert no_inline_code(html)


def returns_303_and_hold_with_birth_date_1985_03_14_when_parts_are_14_3_1985() -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), _details_form())

    assert response.status_code == 303
    assert BookingHold.objects.get().visitor_birth_date == date(1985, 3, 14)


def returns_422_with_one_error_and_typed_values_when_year_is_empty() -> None:
    clinic = make_clinic()

    response = browser_post(
        browser_client(), details_path(clinic), _details_form(date_of_birth_year="")
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert html.count("Enter a year") == 2
    assert 'id="id_date_of_birth_day"' in html
    assert re.search(r'id="id_date_of_birth_day"[^>]*value="14"', html)
    assert re.search(r'id="id_date_of_birth_month"[^>]*value="3"', html)
    assert 'href="#id_date_of_birth_day"' not in html.replace("id_date_of_birth_year", "")
    assert BookingHold.objects.count() == 0


def returns_422_and_reflects_nothing_unescaped_when_a_part_holds_a_script_tag() -> None:
    clinic = make_clinic()

    response = browser_post(
        browser_client(),
        details_path(clinic),
        _details_form(date_of_birth_day="<script>alert(1)</script>"),
    )

    assert response.status_code == 422
    assert "<script>alert(1)" not in response.content.decode()


def returns_stored_birth_date_split_in_three_values_when_profile_is_opened() -> None:
    patient = _patient(email="pat.dob@example.test", role="PATIENT", date_of_birth=date(1990, 2, 3))

    html = signed_in_patient(patient).get(PROFILE).content.decode()

    assert re.search(r'id="id_date_of_birth_day"[^>]*value="3"', html)
    assert re.search(r'id="id_date_of_birth_month"[^>]*value="2"', html)
    assert re.search(r'id="id_date_of_birth_year"[^>]*value="1990"', html)
    assert 'type="date"' not in html


def returns_birth_date_saved_when_profile_parts_are_posted() -> None:
    patient = _patient(email="pat.dob2@example.test", role="PATIENT", phone="")
    client = signed_in_patient(patient)

    response = browser_post(client, PROFILE, {"phone": "", **PARTS})

    patient.refresh_from_db()
    assert response.status_code in (200, 302, 303)
    assert patient.date_of_birth == date(1985, 3, 14)


def returns_profile_saved_with_no_birth_date_when_all_three_parts_are_empty() -> None:
    patient = _patient(
        email="pat.dob3@example.test", role="PATIENT", date_of_birth=date(1990, 2, 3)
    )
    client = signed_in_patient(patient)
    empty = {"date_of_birth_day": "", "date_of_birth_month": "", "date_of_birth_year": ""}

    browser_post(client, PROFILE, {"phone": "", **empty})

    patient.refresh_from_db()
    assert patient.date_of_birth is None


def returns_422_with_group_error_when_profile_date_does_not_exist() -> None:
    patient = _patient(email="pat.dob4@example.test", role="PATIENT")
    client = signed_in_patient(patient)

    response = browser_post(
        client,
        PROFILE,
        {"phone": "", **PARTS, "date_of_birth_day": "31", "date_of_birth_month": "4"},
    )

    assert response.status_code == 422
    assert response.content.decode().count("That date does not exist") == 2


def returns_422_asking_for_a_date_of_birth_when_all_three_booking_parts_are_empty() -> None:
    empty = {"date_of_birth_day": "", "date_of_birth_month": "", "date_of_birth_year": ""}

    response = browser_post(browser_client(), details_path(make_clinic()), _details_form(**empty))

    assert response.status_code == 422
    assert "Enter your date of birth." in response.content.decode()
    assert BookingHold.objects.count() == 0


def returns_summary_link_to_the_day_input_when_profile_date_is_wrong() -> None:
    patient = _patient(email="pat.dob5@example.test", role="PATIENT")

    response = browser_post(
        signed_in_patient(patient),
        PROFILE,
        {"phone": "", **PARTS, "date_of_birth_day": "31", "date_of_birth_month": "4"},
    )

    html = response.content.decode()
    assert 'href="#id_date_of_birth_day"' in html
    assert 'href="#id_date_of_birth"' not in html


def returns_group_described_by_hint_and_error_when_birth_date_is_wrong() -> None:
    response = browser_post(
        browser_client(), details_path(make_clinic()), _details_form(date_of_birth_year="")
    )

    fieldset = re.search(r"<fieldset[^>]*date-group[^>]*>", response.content.decode())
    assert fieldset is not None
    assert 'aria-describedby="id_date_of_birth_hint id_date_of_birth_error"' in fieldset.group(0)
