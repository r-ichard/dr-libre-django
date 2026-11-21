"""Task 17: availability, time off, patients and rooms pages, as a browser sends them."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from django.test import Client

from scheduling.models import Appointment, AvailabilityRule, TimeOff, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient
from scheduling.views.pages.browser_support import (
    NULL_ORIGIN,
    OTHER_SITE_ORIGIN,
    browser_post,
)

pytestmark = pytest.mark.django_db

OWN_PATIENT = "Own Visiting Patient"
OTHER_PATIENT = "Strangers Patient Name"
STRANGER_PHONE = "+49 30 5550 999"
PAGES = [
    "/clinician/availability",
    "/clinician/time-off",
    "/clinician/patients",
    "/clinician/rooms",
]
RULE_FORM = {
    "weekday": "3",
    "start_time": "10:00",
    "end_time": "12:00",
    "slot_step_minutes": "30",
    "room": "",
}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _client(clinic: Clinic) -> Client:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return signed_in_patient(user)


def _visit(clinic: Clinic, name: str, clinician: object = None, **fields: object) -> Appointment:
    patient = make(
        "User", full_name=name, phone=STRANGER_PHONE if name == OTHER_PATIENT else "+49 30 1111 222"
    )
    starts_at = fields.pop("starts_at", STARTS_AT)
    assert isinstance(starts_at, datetime)
    row = make(
        "Appointment",
        patient=patient,
        clinician=clinician or clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        **fields,
    )
    assert isinstance(row, Appointment)
    return row


@pytest.mark.parametrize("path", PAGES)
def returns_200_no_store_and_clean_markup_when_clinician_opens_page(path: str) -> None:
    clinic = make_clinic()

    response = _client(clinic).get(path)

    html = response.content.decode()
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert no_inline_code(html)
    assert len(re.findall(r"<h1\b", html)) == 1


@pytest.mark.parametrize("path", PAGES)
def rejects_patient_and_visitor_when_opening_clinician_page(path: str) -> None:
    clinic = make_clinic()

    assert signed_in_patient(clinic.patient).get(path).status_code == 403
    assert Client().get(path).status_code in {302, 401, 403}


def returns_links_new_sections_with_aria_current_when_on_availability() -> None:
    html = _client(make_clinic()).get("/clinician/availability").content.decode()

    for path in PAGES:
        assert f'href="{path}"' in html
    assert re.search(r'href="/clinician/availability"[^>]*aria-current="page"', html)


def returns_shows_weekday_by_name_in_rule_list() -> None:
    html = _client(make_clinic()).get("/clinician/availability").content.decode()

    assert "Monday" in html and "09:00" in html and "17:00" in html


def returns_creates_rule_and_redirects_303_when_browser_posts_form() -> None:
    clinic = make_clinic()

    response = browser_post(_client(clinic), "/clinician/availability/new", RULE_FORM)

    assert response.status_code == 303
    assert AvailabilityRule.objects.filter(clinician=clinic.clinician, weekday=3).count() == 1


@pytest.mark.parametrize("origin", [OTHER_SITE_ORIGIN, NULL_ORIGIN])
def returns_403_and_no_rule_when_form_comes_from_other_origin(origin: str) -> None:
    clinic = make_clinic()

    response = browser_post(_client(clinic), "/clinician/availability/new", RULE_FORM, origin)

    assert response.status_code == 403
    assert AvailabilityRule.objects.filter(clinician=clinic.clinician).count() == 1


def returns_422_with_error_summary_when_rule_overlaps() -> None:
    clinic = make_clinic()
    overlapping = {**RULE_FORM, "weekday": "1", "start_time": "16:00", "end_time": "18:00"}

    response = browser_post(_client(clinic), "/clinician/availability/new", overlapping)

    assert response.status_code == 422
    assert "error-summary" in response.content.decode()


def returns_403_when_clinician_edits_other_clinicians_rule() -> None:
    clinic = make_clinic()
    foreign = AvailabilityRule.objects.get(clinician=add_clinician(clinic.department))

    response = browser_post(_client(clinic), f"/clinician/availability/{foreign.pk}/delete", {})

    assert response.status_code == 403
    assert AvailabilityRule.objects.filter(pk=foreign.pk).exists()


def returns_deletes_own_rule_when_browser_posts_confirmation() -> None:
    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)

    response = browser_post(_client(clinic), f"/clinician/availability/{rule.pk}/delete", {})

    assert response.status_code == 303
    assert not AvailabilityRule.objects.filter(pk=rule.pk).exists()


def returns_says_time_off_does_not_cancel_appointments_on_time_off_page() -> None:
    html = _client(make_clinic()).get("/clinician/time-off").content.decode()

    assert "Time off does not cancel appointments already booked in it." in html


def returns_creates_time_off_when_browser_posts_form() -> None:
    clinic = make_clinic()
    form = {"starts_at": "2030-02-01T09:00", "ends_at": "2030-02-01T12:00", "reason": "Course"}

    response = browser_post(_client(clinic), "/clinician/time-off", form)

    assert response.status_code == 303
    assert TimeOff.objects.filter(clinician=clinic.clinician, reason="Course").count() == 1


def returns_lists_appointment_inside_period_without_recording_when_previewing() -> None:
    clinic = make_clinic()
    _visit(clinic, OWN_PATIENT)
    query = "starts_at=2030-01-07T10:00&ends_at=2030-01-07T14:00"

    html = _client(clinic).get(f"/clinician/time-off?{query}").content.decode()

    assert OWN_PATIENT in html
    assert TimeOff.objects.filter(clinician=clinic.clinician).count() == 0


def returns_403_when_clinician_deletes_other_clinicians_time_off() -> None:
    clinic = make_clinic()
    foreign = make("TimeOff", clinician=add_clinician(clinic.department))

    response = browser_post(_client(clinic), f"/clinician/time-off/{foreign.pk}/delete", {})

    assert response.status_code == 403
    assert TimeOff.objects.filter(pk=foreign.pk).exists()


@pytest.mark.parametrize(
    "search", ["", "Strangers", "Strangers Patient Name", "%", "_", "*", "Own"]
)
def returns_lists_only_own_patients_whatever_the_search(search: str) -> None:
    clinic = make_clinic()
    _visit(clinic, OWN_PATIENT)
    _visit(clinic, OTHER_PATIENT, clinician=add_clinician(clinic.department))

    html = _client(clinic).get("/clinician/patients", {"q": search}).content.decode()

    assert OTHER_PATIENT not in html and STRANGER_PHONE not in html


def returns_lists_patient_with_phone_last_and_next_visit() -> None:
    clinic = make_clinic()
    _visit(clinic, OWN_PATIENT, starts_at=NOW - timedelta(days=2))
    _visit(clinic, OWN_PATIENT, starts_at=NOW + timedelta(days=3))

    html = _client(clinic).get("/clinician/patients").content.decode()

    assert OWN_PATIENT in html and "+49 30 1111 222" in html
    assert "2030-01-05" in html or "5 Jan 2030" in html
    assert "2030-01-10" in html or "10 Jan 2030" in html


def returns_shows_name_for_own_and_only_occupied_for_other_clinician_in_rooms() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department, name="Heart room")
    make("Room", department=clinic.department, name="Retired room", is_active=False)
    _visit(clinic, OWN_PATIENT, room=room)
    other = add_clinician(clinic.department)
    _visit(
        clinic,
        OTHER_PATIENT,
        clinician=other,
        room=room,
        patient_reason="planted-secret-reason",
        starts_at=STARTS_AT + timedelta(hours=2),
    )

    html = _client(clinic).get("/clinician/rooms?date=2030-01-07").content.decode()

    assert OWN_PATIENT in html and "Heart room" in html and "Occupied" in html
    assert "Retired room" not in html
    for secret in (OTHER_PATIENT, STRANGER_PHONE, "planted-secret-reason"):
        assert secret not in html


def returns_200_without_retired_room_appointment_in_rooms_timeline() -> None:
    clinic = make_clinic()
    make("Room", department=clinic.department, name="Heart room")
    retired = make("Room", department=clinic.department, name="Retired room", is_active=False)
    _visit(clinic, OWN_PATIENT, room=retired)

    response = _client(clinic).get("/clinician/rooms?date=2030-01-07")

    assert response.status_code == 200
    assert OWN_PATIENT not in response.content.decode()


def returns_matches_long_name_only_up_to_hundred_characters_of_search() -> None:
    clinic = make_clinic()
    long_name = "A" * 100
    _visit(clinic, long_name)

    html = _client(clinic).get("/clinician/patients", {"q": long_name + "B"}).content.decode()

    assert long_name in html


def returns_labels_hours_0700_to_1900_and_24_rows_in_time_grid() -> None:
    clinic = make_clinic()
    make("Room", department=clinic.department, name="Grid room")

    html = _client(clinic).get("/clinician/rooms?date=2030-01-07").content.decode()

    for hour in range(7, 20):
        assert f"{hour:02d}:00" in html
    assert len(re.findall(r'class="[^"]*\btime-grid-row\b', html)) == 24
    assert "Grid room" in html


def returns_names_the_zone_beside_times_in_appointment_history() -> None:
    clinic = make_clinic()
    visit = _visit(clinic, OWN_PATIENT)

    html = _client(clinic).get(f"/clinician/appointments/{visit.pk}").content.decode()

    assert re.search(r"\b\d\d:\d\d(:\d\d)? (CET|CEST)\b", html) or "Europe/Berlin" in html
