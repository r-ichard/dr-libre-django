"""Section 7.1: the confirmation and calendar file, only for the appointment's patient."""

from __future__ import annotations

import pytest
from django.test import Client

from scheduling.models import Appointment
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _booked(clinic: Clinic, **overrides: object) -> Appointment:
    fields = {
        "patient": clinic.patient,
        "clinician": clinic.clinician,
        "appointment_type": clinic.appointment_type,
        "patient_reason": "Private reason",
        **overrides,
    }
    appointment = make("Appointment", **fields)
    assert isinstance(appointment, Appointment)
    make("ClinicalNote", appointment=appointment, clinical_notes="Private notes")
    return appointment


def returns_provider_when_zone_hospital_address_department_and_calendar_link_are_shown() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)

    page = signed_in_patient(clinic.patient).get(f"/appointments/{appointment.pk}/confirmation")

    html = page.content.decode()
    assert page.status_code == 200
    assert "Monday 7 January 2030" in html
    assert "11:00" in html and "11:30" in html
    assert "Europe/Berlin" in html
    assert "Riverside Hospital" in html and "1 River Road" in html
    assert clinic.department.name in html
    assert "confirmation email" in html
    assert f"/appointments/{appointment.pk}/calendar.ics" in html
    assert 'href="/patient/"' in html
    assert "Private reason" not in html
    assert no_inline_code(html)
    assert "no-store" in page["Cache-Control"]


def returns_no_room_when_none_assigned() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)

    html = (
        signed_in_patient(clinic.patient)
        .get(f"/appointments/{appointment.pk}/confirmation")
        .content.decode()
    )

    assert "Riverside Hospital" in html
    assert "Room" not in html


def returns_403_when_another_patient_opens_it() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)
    other = make("User")

    response = signed_in_patient(other).get(f"/appointments/{appointment.pk}/confirmation")  # type: ignore[arg-type]

    owner = signed_in_patient(clinic.patient).get(f"/appointments/{appointment.pk}/confirmation")
    assert (owner.status_code, response.status_code) == (200, 403)


def returns_redirect_to_sign_in_when_not_signed_in() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)

    response = Client().get(f"/appointments/{appointment.pk}/confirmation")

    assert response.status_code == 302
    assert response["Location"].startswith("/sign-in")


def returns_text_calendar_attachment_with_utc_times_location_and_no_reason_or_notes() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)

    response = signed_in_patient(clinic.patient).get(f"/appointments/{appointment.pk}/calendar.ics")

    text = response.content.decode()
    assert response["Content-Type"].startswith("text/calendar")
    assert "attachment" in response["Content-Disposition"]
    assert "DTSTART:20300107T100000Z" in text
    assert "DTEND:20300107T103000Z" in text
    assert "1 River Road" in text
    assert "Private" not in text
    assert "no-store" in response["Cache-Control"]


def returns_403_for_other_patient_and_404_for_cancelled_appointment() -> None:
    clinic = make_clinic()
    other = make("User")
    live = _booked(clinic)
    cancelled = _booked(
        clinic, status="CANCELLED", cancellation_reason="Moved away", cancelled_at=NOW
    )

    stranger = signed_in_patient(other).get(f"/appointments/{live.pk}/calendar.ics")  # type: ignore[arg-type]
    owner = signed_in_patient(clinic.patient).get(f"/appointments/{cancelled.pk}/calendar.ics")

    live_owner = signed_in_patient(clinic.patient).get(f"/appointments/{live.pk}/calendar.ics")
    assert (live_owner.status_code, stranger.status_code, owner.status_code) == (200, 403, 404)


def returns_404_when_confirmation_or_calendar_id_does_not_exist() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)
    missing = "00000000-0000-4000-8000-000000000000"

    codes = [
        client.get(f"/appointments/{missing}/{leaf}").status_code
        for leaf in ("confirmation", "calendar.ics")
    ]

    assert codes == [404, 404]


def returns_403_when_calendar_file_belongs_to_another_patient() -> None:
    clinic = make_clinic()
    appointment = _booked(clinic)

    response = signed_in_patient(make("User")).get(f"/appointments/{appointment.pk}/calendar.ics")  # type: ignore[arg-type]

    assert response.status_code == 403
    assert b"BEGIN:VCALENDAR" not in response.content
