"""Task 20, items 1, 2 and 5: the admin appointment list and the appointment page, as a browser
sends them. Routes: /admin-console/appointments[/<id>[/<action>]]."""

import re
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.models import Appointment, AuditLogEntry, Notification
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post, client_of_role

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LIST = "/admin-console/appointments"
PAGE_SIZE = 20
PLANTED_NOTE = "planted-clinical-note-8841"


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _appointment(**overrides: object) -> Appointment:
    row = make("Appointment", **overrides)
    assert isinstance(row, Appointment)
    return row


def _spread(count: int) -> None:
    clinic = make_clinic()
    for index in range(count):
        start = NOW + timedelta(days=1 + index)
        _appointment(
            clinician=clinic.clinician, appointment_type=clinic.appointment_type,
            starts_at=start, ends_at=start + timedelta(minutes=30),
        )  # fmt: skip


def _body_rows(html: str) -> int:
    body = html.partition("<tbody")[2]
    return len(re.findall(r"<tr[ >]", body))


def returns_twenty_rows_newest_first_with_the_total_when_the_list_is_opened() -> None:
    _spread(PAGE_SIZE + 5)

    html = admin_client().get(LIST).content.decode()

    assert _body_rows(html) == PAGE_SIZE
    assert "25 appointments" in html
    newest = (NOW + timedelta(days=25)).strftime("%Y-%m-%d")
    oldest_on_page_two = (NOW + timedelta(days=1)).strftime("%Y-%m-%d")
    assert newest in html and oldest_on_page_two not in html


def returns_the_time_in_the_hospital_zone_named_when_the_list_is_opened() -> None:
    _appointment()

    html = admin_client().get(LIST).content.decode()

    assert "11:00" in html and "Europe/Berlin" in html


def returns_only_the_status_asked_and_keeps_it_in_the_pagination_when_filtered() -> None:
    _spread(PAGE_SIZE + 2)
    _appointment(status="CHECKED_IN")

    html = admin_client().get(f"{LIST}?status=BOOKED").content.decode()

    assert "22 appointments" in html
    assert "status=BOOKED" in html.split("pagination", 1)[1]


def returns_only_the_source_asked_when_filtered() -> None:
    _appointment(source="STAFF")
    _appointment(source="ONLINE")
    _appointment(source="ONLINE")

    html = admin_client().get(f"{LIST}?source=STAFF").content.decode()

    assert "1 appointment" in html and "3 appointments" not in html


def returns_only_the_clinician_and_department_asked_when_filtered() -> None:
    first, second = make_clinic(), make_clinic()
    for clinic in (first, second):
        _appointment(clinician=clinic.clinician, appointment_type=clinic.appointment_type)

    by_clinician = admin_client().get(f"{LIST}?clinician={first.clinician.pk}")
    by_department = admin_client().get(f"{LIST}?department={second.department.pk}")

    assert "1 appointment" in by_clinician.content.decode()
    assert "1 appointment" in by_department.content.decode()
    assert _body_rows(by_clinician.content.decode()) == 1
    assert _body_rows(by_department.content.decode()) == 1


def returns_the_default_list_with_200_when_the_filters_are_unusable() -> None:
    _appointment()
    address = f"{LIST}?from=nope&to=2030-13-45&status=EATEN&source=x&clinician=1&page=-3"

    response = admin_client().get(address)

    assert response.status_code == 200
    assert "1 appointment" in response.content.decode()


def returns_the_day_of_a_late_local_start_when_the_range_ends_that_day() -> None:
    late = datetime(2030, 1, 8, 22, 30, tzinfo=UTC)  # 23:30 in Berlin
    _appointment(starts_at=late, ends_at=late + timedelta(minutes=30))

    html = admin_client().get(f"{LIST}?from=2030-01-08&to=2030-01-08").content.decode()

    assert "1 appointment" in html


def returns_no_store_cache_headers_when_the_list_is_opened() -> None:
    response = admin_client().get(LIST)

    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]


def returns_every_detail_and_no_clinical_note_when_one_appointment_is_opened() -> None:
    patient = make("User", full_name="Pat Visible")
    appointment = _appointment(patient=patient, patient_reason="Sore knee")
    make("ClinicalNote", appointment=appointment, clinical_notes=PLANTED_NOTE)

    html = admin_client().get(f"{LIST}/{appointment.pk}").content.decode()

    assert "Pat Visible" in html and "Sore knee" in html and "BOOKED" in html.upper()
    assert appointment.clinician.user.full_name in html
    assert PLANTED_NOTE not in html


def _actions_offered(appointment: Appointment) -> set[str]:
    html = admin_client().get(f"{LIST}/{appointment.pk}").content.decode()
    names = ("check-in", "complete", "no-show", "cancel", "reschedule")
    assert appointment.status.replace("_", " ").lower() in html.lower()
    return {name for name in names if f"{appointment.pk}/{name}" in html}


def returns_check_in_no_show_cancel_and_reschedule_when_the_appointment_is_booked() -> None:
    assert _actions_offered(_appointment()) == {"check-in", "no-show", "cancel", "reschedule"}


def returns_complete_and_cancel_when_the_appointment_is_checked_in() -> None:
    assert _actions_offered(_appointment(status="CHECKED_IN")) == {"complete", "cancel"}


def returns_no_action_when_the_appointment_is_completed() -> None:
    assert _actions_offered(_appointment(status="COMPLETED")) == set()


def returns_checked_in_when_an_admin_checks_in_a_booked_appointment() -> None:
    appointment = _appointment()

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/check-in", {})

    appointment.refresh_from_db()
    assert response.status_code == 303 and appointment.status == "CHECKED_IN"


def returns_completed_when_an_admin_completes_a_checked_in_appointment() -> None:
    appointment = _appointment(status="CHECKED_IN")

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/complete", {})

    appointment.refresh_from_db()
    assert response.status_code == 303 and appointment.status == "COMPLETED"


def returns_no_show_when_an_admin_marks_a_booked_appointment() -> None:
    appointment = _appointment()

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/no-show", {})

    appointment.refresh_from_db()
    assert response.status_code == 303 and appointment.status == "NO_SHOW"


def returns_404_when_an_action_names_an_appointment_that_does_not_exist() -> None:
    missing = "01a20121-f14a-79dc-95e5-b1b18281257e"

    response = admin_post(admin_client(), f"{LIST}/{missing}/check-in", {})

    assert response.status_code == 404


def returns_422_and_every_error_when_cancel_has_no_reason() -> None:
    appointment = _appointment()

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/cancel", {"reason": "  "})

    appointment.refresh_from_db()
    assert response.status_code == 422 and appointment.status == "BOOKED"
    assert "error-summary" in response.content.decode()


def returns_cancelled_with_the_reason_when_an_admin_cancels() -> None:
    appointment = _appointment()

    response = admin_post(
        admin_client(), f"{LIST}/{appointment.pk}/cancel", {"reason": "Clinician ill"}
    )

    appointment.refresh_from_db()
    assert response.status_code == 303 and appointment.status == "CANCELLED"
    assert appointment.cancellation_reason == "Clinician ill"
    assert AuditLogEntry.objects.filter(action="appointment.cancel").exists()


def returns_409_with_a_way_forward_when_a_completed_appointment_is_cancelled() -> None:
    appointment = _appointment(status="COMPLETED")

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/cancel", {"reason": "x"})

    html = response.content.decode()
    assert response.status_code == 409
    assert f"{LIST}/{appointment.pk}" in html
    assert "This appointment is completed, so it cannot be cancelled." in html


def returns_403_page_to_a_patient_and_no_cancel_when_a_patient_posts_a_cancel() -> None:
    appointment = _appointment()

    response = admin_post(
        client_of_role("PATIENT"), f"{LIST}/{appointment.pk}/cancel", {"reason": "mine"}
    )

    appointment.refresh_from_db()
    assert response.status_code == 403 and appointment.status == "BOOKED"


def returns_409_and_the_booked_sentence_when_an_admin_completes_a_booked_appointment() -> None:
    appointment = _appointment()
    audits, notices = AuditLogEntry.objects.count(), Notification.objects.count()

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/complete", {})

    appointment.refresh_from_db()
    assert response.status_code == 409
    assert "This appointment is booked, so it cannot be completed." in response.content.decode()
    assert appointment.status == "BOOKED"
    assert (AuditLogEntry.objects.count(), Notification.objects.count()) == (audits, notices)


def returns_409_and_the_checked_in_sentence_when_an_admin_checks_in_twice() -> None:
    appointment = _appointment(status="CHECKED_IN")
    audits, notices = AuditLogEntry.objects.count(), Notification.objects.count()

    response = admin_post(admin_client(), f"{LIST}/{appointment.pk}/check-in", {})

    appointment.refresh_from_db()
    assert response.status_code == 409
    assert "This appointment is checked in, so it cannot be checked in." in (
        response.content.decode()
    )
    assert appointment.status == "CHECKED_IN"
    assert (AuditLogEntry.objects.count(), Notification.objects.count()) == (audits, notices)
