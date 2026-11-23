"""Section 4: text a browser sends from a form, `\\r\\n` line breaks, and the message a
refusal shows."""

from __future__ import annotations

import pytest

from scheduling.models import ClinicianProfile, Department, Hospital, User
from scheduling.models.builders import make, make_clinic
from scheduling.views.pages.admin_support import admin_client, admin_post
from scheduling.views.pages.browser_support import browser_post
from scheduling.views.pages.test_admin_records_pages import HOSPITAL_FORM
from scheduling.views.pages.test_clinician_workspace import _appointment, _clinician_client

pytestmark = pytest.mark.django_db

CONSOLE = "/admin-console"
TWO_PARAGRAPHS = "First paragraph.\r\n\r\n\tSecond paragraph."
FORM_FEED_NOTE = "Dear doctor\x0cthanks"


def returns_303_and_both_paragraphs_when_hospital_description_has_crlf_blank_line_and_tab() -> None:
    form = {**HOSPITAL_FORM, "description": TWO_PARAGRAPHS}

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/new", form)

    assert response.status_code == 303
    assert Hospital.objects.get(code="saint-anne").description == TWO_PARAGRAPHS


def returns_303_and_both_paragraphs_when_department_description_has_crlf_and_tab() -> None:
    form = {
        "name": "Imaging",
        "code": "Imaging",
        "description": TWO_PARAGRAPHS,
        "hospital": str(make("Hospital").pk),
    }

    response = admin_post(admin_client(), f"{CONSOLE}/departments/new", form)

    assert response.status_code == 303
    assert Department.objects.get(code="imaging").description == TWO_PARAGRAPHS


def returns_422_saying_one_line_on_name_when_hospital_name_has_a_line_break() -> None:
    form = {**HOSPITAL_FORM, "name": "Saint\r\nAnne"}

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/new", form)

    assert response.status_code == 422
    assert "This field takes one line." in response.content.decode()


def returns_the_rules_message_on_clinical_notes_when_a_note_has_a_form_feed() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(
        client,
        f"/clinician/appointments/{appointment.pk}/notes",
        {"clinical_notes": FORM_FEED_NOTE},
    )

    page = response.content.decode()
    assert response.status_code == 422
    assert "Remove the character after &quot;Dear doctor&quot;." in page
    assert "Use at most 5000 characters." not in page


def returns_303_and_both_paragraphs_when_clinician_bio_has_crlf_blank_line_and_tab() -> None:
    user = make("User", role="CLINICIAN")
    assert isinstance(user, User)
    form = {
        "user": str(user.pk),
        "department": str(make("Department").pk),
        "specialty": str(make("Specialty").pk),
        "title": "Dr",
        "bio": TWO_PARAGRAPHS,
        "default_room": "",
        "round_robin_weight": "1",
    }

    response = admin_post(admin_client(), f"{CONSOLE}/clinicians/new", form)

    assert response.status_code == 303
    assert ClinicianProfile.objects.get(user=user).bio == TWO_PARAGRAPHS
