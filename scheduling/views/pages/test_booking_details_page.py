"""Section 7.1: the details and review form, the hold, the patient shortcut."""

from __future__ import annotations

import re

import pytest

from scheduling.models import Appointment, BookingHold
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import (
    FORM,
    NOW,
    VISITOR_EMAIL,
    details_path,
    no_inline_code,
    signed_in_patient,
)
from scheduling.views.pages.browser_support import (
    NULL_ORIGIN,
    browser_client,
    browser_post,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_form_with_six_labelled_fields_and_chosen_appointment_when_visitor_opens_details() -> (
    None
):
    clinic = make_clinic()

    html = browser_client().get(details_path(clinic)).content.decode()

    for name in ["full_name", "date_of_birth_day", "email", "phone", "reason", "terms_accepted"]:
        assert re.search(rf'<label[^>]*for="id_{name}"', html), name
        assert re.search(rf'id="id_{name}"', html), name
    assert clinic.appointment_type.name in html
    assert no_inline_code(html)


def returns_303_to_code_page_and_creates_hold_when_details_are_valid() -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), FORM)

    assert response.status_code == 303
    hold = BookingHold.objects.get()
    assert response["Location"] == f"/book/holds/{hold.pk}/code"


def returns_field_errors_tied_by_aria_and_first_invalid_focused_when_details_are_invalid() -> None:
    clinic = make_clinic()

    response = browser_post(
        browser_client(), details_path(clinic), {**FORM, "full_name": "", "email": "nope"}
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert re.search(r'id="id_full_name"[^>]*aria-describedby="[^"]*error', html)
    assert html.count("data-autofocus") == 1
    assert re.search(r'<[^>]*id="id_full_name"[^>]*data-autofocus', html)
    assert BookingHold.objects.count() == 0


def returns_403_when_post_has_wrong_origin() -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), FORM, origin=NULL_ORIGIN)

    assert response.status_code == 403
    assert BookingHold.objects.count() == 0


def returns_review_page_without_details_form_when_patient_is_signed_in() -> None:
    clinic = make_clinic()

    html = signed_in_patient(clinic.patient).get(details_path(clinic)).content.decode()

    assert 'id="id_reason"' in html
    assert 'id="id_full_name"' not in html
    assert "Confirm" in html


def returns_303_to_confirmation_and_books_when_patient_confirms() -> None:
    clinic = make_clinic()

    response = browser_post(signed_in_patient(clinic.patient), details_path(clinic), {"reason": ""})

    appointment = Appointment.objects.get()
    assert response.status_code == 303
    assert response["Location"] == f"/appointments/{appointment.pk}/confirmation"


def returns_403_page_when_clinician_opens_booking() -> None:
    clinic = make_clinic()

    response = signed_in_patient(clinic.clinician.user).get(details_path(clinic))

    assert response.status_code == 403


def returns_slot_taken_page_409_with_times_link_when_slot_taken_between_page_and_post() -> None:
    clinic = make_clinic()
    browser_post(browser_client(), details_path(clinic), FORM)

    response = browser_post(
        browser_client(), details_path(clinic), {**FORM, "email": "other@example.test"}
    )

    html = response.content.decode()
    assert response.status_code == 409
    assert "That time was just taken." in html
    assert "See the refreshed times" in html


def returns_no_email_in_address_when_hold_is_created() -> None:
    clinic = make_clinic()

    response = browser_post(browser_client(), details_path(clinic), FORM)

    assert VISITOR_EMAIL not in response["Location"]
    assert "Vera" not in response["Location"]
