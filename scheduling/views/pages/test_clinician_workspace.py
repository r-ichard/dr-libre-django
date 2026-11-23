"""Section 9: clinician's today, calendar and appointment pages, as a browser sends them."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client

from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, Notification, User
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient
from scheduling.views.pages.browser_support import (
    NULL_ORIGIN,
    OTHER_SITE_ORIGIN,
    browser_post,
)

pytestmark = pytest.mark.django_db

TODAY_PATH = "/clinician/?date=2030-01-07"
PLANTED_NOTE = "planted-clinical-note-6618"
PLANTED_NAME = "Planted Patient Name"
PLANTED_PHONE = "+49 30 7777 123"
PLANTED_REASON = "planted-visit-reason-4410"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _clinician_client(clinic: Clinic) -> Client:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return signed_in_patient(user)


def _appointment(clinic: Clinic, **overrides: object) -> Appointment:
    clinic.patient.full_name = PLANTED_NAME
    clinic.patient.phone = PLANTED_PHONE
    clinic.patient.date_of_birth = NOW.date().replace(year=1990, month=5, day=1)
    clinic.patient.save()
    fields = {
        "patient": clinic.patient,
        "clinician": clinic.clinician,
        "appointment_type": clinic.appointment_type,
        "patient_reason": PLANTED_REASON,
        "starts_at": STARTS_AT,
        "ends_at": STARTS_AT + timedelta(minutes=30),
        **overrides,
    }
    if fields.get("status") == "CANCELLED":
        fields = {"cancelled_at": NOW, "cancellation_reason": "Moved", **fields}
    row = make("Appointment", **fields)
    assert isinstance(row, Appointment)
    return row


def _save_note(clinic: Clinic, appointment: Appointment) -> None:
    from scheduling.use_cases.clinical_notes import save_clinical_note

    actor = clinic.clinician.user
    assert isinstance(actor, User)
    with bind_request_context(RequestContext("corr-plant", NOW)):
        save_clinical_note(appointment.pk, PLANTED_NOTE, actor)


def _forms_of(html: str) -> list[str]:
    return re.findall(r'<form[^>]*action="([^"]+)"', html)


# --- today ---


def returns_agenda_row_with_patient_type_room_and_status_when_day_has_appointment() -> None:
    clinic = make_clinic()
    _appointment(clinic)

    html = _clinician_client(clinic).get(TODAY_PATH).content.decode()

    assert PLANTED_NAME in html
    assert clinic.appointment_type.name in html
    assert "Booked" in html
    assert "<h2" in html and "11:00" in html
    assert no_inline_code(html)


def returns_tiles_with_exact_counts_when_day_has_mixed_statuses() -> None:
    clinic = make_clinic()
    for index, status in enumerate(["BOOKED", "CHECKED_IN", "COMPLETED", "NO_SHOW", "CANCELLED"]):
        start = STARTS_AT + timedelta(hours=index)
        _appointment(clinic, status=status, starts_at=start, ends_at=start + timedelta(minutes=30))

    html = _clinician_client(clinic).get(TODAY_PATH).content.decode()

    assert re.search(r"Appointments\W+(<[^>]+>\s*)*2\b", html)
    assert re.search(r"Cancelled\W+(<[^>]+>\s*)*1\b", html)
    assert re.search(r"Completed\W+(<[^>]+>\s*)*1\b", html)
    assert re.search(r"No-shows?\W+(<[^>]+>\s*)*1\b", html)


def returns_exactly_the_status_forms_the_table_allows_when_booked() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    html = _clinician_client(clinic).get(TODAY_PATH).content.decode()

    base = f"/clinician/appointments/{appointment.pk}"
    assert f"{base}/check-in" in _forms_of(html)
    assert f"{base}/no-show" in _forms_of(html)
    assert f"{base}/complete" not in _forms_of(html)


def returns_complete_and_no_check_in_when_checked_in() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic, status="CHECKED_IN")

    html = _clinician_client(clinic).get(TODAY_PATH).content.decode()

    base = f"/clinician/appointments/{appointment.pk}"
    assert f"{base}/complete" in _forms_of(html)
    assert f"{base}/check-in" not in _forms_of(html)


def returns_previous_next_and_today_when_viewing_a_day() -> None:
    html = _clinician_client(make_clinic()).get(TODAY_PATH).content.decode()

    assert "?date=2030-01-06" in html
    assert "?date=2030-01-08" in html
    assert "?date=2030-01-07" in html


def returns_only_own_appointments_when_two_clinicians_share_a_day() -> None:
    clinic = make_clinic()
    other = make_clinic()
    _appointment(other, patient_reason="other-clinician-reason")

    html = _clinician_client(clinic).get(TODAY_PATH).content.decode()

    assert PLANTED_NAME not in html


def returns_in_and_redirects_when_form_is_posted_as_a_browser_sends_it() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(client, f"/clinician/appointments/{appointment.pk}/check-in", {})

    appointment.refresh_from_db()
    assert response.status_code == 303
    assert appointment.status == "CHECKED_IN"


@pytest.mark.parametrize("origin", [OTHER_SITE_ORIGIN, NULL_ORIGIN])
def returns_403_and_keeps_status_when_origin_is_not_this_site(origin: str) -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(
        client, f"/clinician/appointments/{appointment.pk}/check-in", {}, origin=origin
    )

    appointment.refresh_from_db()
    assert response.status_code == 403
    assert appointment.status == "BOOKED"


# --- calendar ---


def returns_block_naming_type_and_patient_with_colour_class_when_week_has_appointment() -> None:
    clinic = make_clinic()
    _appointment(clinic)

    html = _clinician_client(clinic).get("/clinician/calendar?week=2030-01-07").content.decode()

    assert f">{clinic.appointment_type.name}</span>" in html
    assert f">{PLANTED_NAME}</span>" in html
    assert f"type-colour--{clinic.appointment_type.pk.hex}" in html
    assert html.count("<ol") >= 8
    assert "style=" not in html


def returns_cancelled_appointment_out_when_week_is_shown() -> None:
    clinic = make_clinic()
    _appointment(clinic, status="CANCELLED")

    html = _clinician_client(clinic).get("/clinician/calendar?week=2030-01-07").content.decode()

    assert PLANTED_NAME not in html


def returns_css_rule_per_type_when_signed_in_clinician() -> None:
    clinic = make_clinic()

    response = _clinician_client(clinic).get("/clinician/type-colours.css")

    assert response["Content-Type"].startswith("text/css")
    assert (
        f".type-colour--{clinic.appointment_type.pk.hex} {{ --type-colour: #336699; }}"
        in response.content.decode()
    )


def rejects_type_colours_when_visitor_or_patient() -> None:
    clinic = make_clinic()

    assert Client().get("/clinician/type-colours.css").status_code in {302, 401, 403}
    assert signed_in_patient(clinic.patient).get("/clinician/type-colours.css").status_code == 403


# --- appointment ---


def returns_patient_details_and_history_when_clinician_opens_own_appointment() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)
    browser_post(client, f"/clinician/appointments/{appointment.pk}/check-in", {})

    html = client.get(f"/clinician/appointments/{appointment.pk}").content.decode()

    assert PLANTED_NAME in html and PLANTED_PHONE in html and PLANTED_REASON in html
    assert "39" in html
    assert "Checked in" in html
    assert 'maxlength="5000"' in html


def returns_not_your_appointment_and_nothing_else_when_other_clinician() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    _save_note(clinic, appointment)

    response = _clinician_client(make_clinic()).get(f"/clinician/appointments/{appointment.pk}")

    html = response.content.decode()
    assert response.status_code == 403
    assert "Not your appointment" in html
    for planted in (PLANTED_NAME, PLANTED_PHONE, PLANTED_REASON, PLANTED_NOTE):
        assert planted not in html


def returns_404_when_appointment_does_not_exist() -> None:
    clinic = make_clinic()
    own = _appointment(clinic)
    client = _clinician_client(clinic)
    missing = "00000000-0000-4000-8000-000000000001"

    responses = (
        client.get(f"/clinician/appointments/{own.pk}"),
        client.get(f"/clinician/appointments/{missing}"),
    )

    assert [response.status_code for response in responses] == [200, 404]
    assert "Not your appointment" not in responses[1].content.decode()


def returns_refusal_instead_of_empty_note_box_when_note_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling.domain.failure import Failure
    from scheduling.views.pages import clinician_appointment

    clinic = make_clinic()
    appointment = _appointment(clinic)
    _save_note(clinic, appointment)
    monkeypatch.setattr(clinician_appointment, "read_clinical_note", lambda *_: Failure.forbidden())

    response = _clinician_client(clinic).get(f"/clinician/appointments/{appointment.pk}")

    html = response.content.decode()
    assert response.status_code == 403
    assert "<textarea" not in html


def returns_reason_and_answers_422_when_cancel_form_is_blank() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(
        client, f"/clinician/appointments/{appointment.pk}/cancel", {"reason": " "}
    )

    appointment.refresh_from_db()
    assert response.status_code == 422
    assert appointment.status == "BOOKED"


def returns_when_reason_is_given() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(
        client, f"/clinician/appointments/{appointment.pk}/cancel", {"reason": "Clinic closed"}
    )

    appointment.refresh_from_db()
    assert response.status_code == 303
    assert (appointment.status, appointment.cancellation_reason) == ("CANCELLED", "Clinic closed")


def returns_message_and_way_forward_when_status_changed_since_page_load() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic, status="COMPLETED")
    client = _clinician_client(clinic)

    response = browser_post(client, f"/clinician/appointments/{appointment.pk}/check-in", {})

    html = response.content.decode()
    assert response.status_code == 409
    assert f"/clinician/appointments/{appointment.pk}" in html


# --- clinical notes ---


def returns_note_and_shows_it_to_own_clinician_when_form_is_posted() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)

    response = browser_post(
        client, f"/clinician/appointments/{appointment.pk}/notes", {"clinical_notes": PLANTED_NOTE}
    )

    assert response.status_code == 303
    assert PLANTED_NOTE in client.get(f"/clinician/appointments/{appointment.pk}").content.decode()


def returns_note_out_of_every_other_surface_when_clinician_saved_it() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    _save_note(clinic, appointment)
    patient_client = signed_in_patient(clinic.patient)
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    surfaces = [
        patient_client.get("/patient/appointments"),
        patient_client.get(f"/api/v1/appointments/{appointment.pk}"),
        patient_client.get("/api/v1/appointments"),
        signed_in_patient(admin).get("/admin-console/"),
        _clinician_client(clinic).get("/clinician/type-colours.css"),
    ]

    bodies = [response.content.decode() for response in surfaces]
    stored = [str(entry.metadata) for entry in AuditLogEntry.objects.all()]
    stored += [f"{note.title}{note.body}" for note in Notification.objects.all()]
    stored += [f"{message.subject}{message.body}" for message in mail.outbox]
    assert all(PLANTED_NOTE not in text for text in bodies + stored)


def returns_note_out_of_every_log_line_when_clinician_saves_and_opens_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)
    client = _clinician_client(clinic)
    url = f"/clinician/appointments/{appointment.pk}"

    with caplog.at_level(logging.DEBUG):
        browser_post(client, f"{url}/notes", {"clinical_notes": PLANTED_NOTE})
        shown = client.get(url).content.decode()

    assert PLANTED_NOTE in shown
    assert caplog.records
    assert PLANTED_NOTE not in caplog.text


# --- navigation and caching ---


@pytest.mark.parametrize(
    ("path", "current"),
    [(TODAY_PATH, "Today"), ("/clinician/calendar?week=2030-01-07", "Calendar")],
)
def returns_current_section_when_workspace_navigation_is_shown(path: str, current: str) -> None:
    html = _clinician_client(make_clinic()).get(path).content.decode()

    navigation = re.search(r"<nav[^>]*Clinician workspace.*?</nav>", html, re.DOTALL)
    assert navigation is not None
    assert html.count("<nav") == 1
    assert navigation.group(0).count('aria-current="page"') == 1
    assert re.search(rf'aria-current="page"[^>]*>\s*{current}\b', navigation.group(0))
    for later in ("Availability", "Time off", "Patients", "Rooms"):
        assert later in navigation.group(0)


@pytest.mark.parametrize("path", [TODAY_PATH, "/clinician/calendar?week=2030-01-07"])
def returns_caches_when_page_shows_patient_data(path: str) -> None:
    response = _clinician_client(make_clinic()).get(path)

    assert "no-store" in response["Cache-Control"]


def returns_no_store_when_appointment_page_shows_patient_data() -> None:
    clinic = make_clinic()
    appointment = _appointment(clinic)

    response = _clinician_client(clinic).get(f"/clinician/appointments/{appointment.pk}")

    assert PLANTED_NAME in response.content.decode()
    assert "no-store" in response["Cache-Control"]
