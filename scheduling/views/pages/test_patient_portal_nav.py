"""Task 15: one portal navigation on the five sections, and the refusal for a week strip."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from scheduling.models import User
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient

pytestmark = pytest.mark.django_db

SECTIONS = {
    "/patient/": "Home",
    "/patient/appointments": "Appointments",
    "/patient/waitlist": "Waitlist",
    "/patient/notifications": "Notifications",
    "/patient/profile": "Profile",
}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.mark.parametrize("path", SECTIONS)
def returns_one_navigation_with_five_links_and_the_current_one_marked(path: str) -> None:
    patient = make("User")
    assert isinstance(patient, User)
    html = signed_in_patient(patient).get(path).content.decode()

    portal = re.findall(
        r'<nav class="portal-nav" aria-label="Patient portal">.*?</nav>', html, re.S
    )
    assert len(portal) == 1
    assert portal[0].count("<a ") == len(SECTIONS)
    current = re.findall(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', portal[0])
    assert current == [SECTIONS[path]]
    assert html.count("<h1") == 1


def returns_refusal_page_with_way_back_when_week_strip_cannot_load() -> None:
    clinic = make_clinic(type_fields={"is_active": False})
    starts_at = NOW + timedelta(days=10)
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )

    response = signed_in_patient(clinic.patient).get(
        f"/patient/appointments/{appointment.pk}/reschedule"
    )

    html = response.content.decode()
    assert response.status_code == 404
    assert "We could not load times for this appointment." in html
    assert 'href="/patient/appointments"' in html
