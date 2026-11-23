"""Section 13: the appointment export as a browser sends it. Route:
POST /admin-console/appointments/export, filters in the address like the list."""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from scheduling.models import Appointment, AuditLogEntry
from scheduling.models.builders import Clinic, make, make_clinic, make_user
from scheduling.use_cases import admin_appointment_export
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post, client_of_role

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
EXPORT = "/admin-console/appointments/export"
LIST = "/admin-console/appointments"
COLUMNS = [
    "appointment_id", "start", "end", "status", "source", "patient_id", "clinician_id",
    "department_id", "appointment_type_id", "room_id",
]  # fmt: skip


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _book(clinic: Clinic, hours_ahead: int = 1, status: str = "BOOKED") -> Appointment:
    starts_at = NOW + timedelta(hours=hours_ahead)
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
    )
    assert isinstance(appointment, Appointment)
    return appointment


def _rows(client: Client, query: str = "") -> list[list[str]]:
    response = admin_post(client, EXPORT + query, {})
    assert response.status_code == 200
    return list(csv.reader(io.StringIO(response.content.decode())))


def returns_the_ten_columns_with_utc_instants_and_ids_only_when_exported() -> None:
    clinic = make_clinic()
    appointment = _book(clinic)

    response = admin_post(admin_client(), EXPORT, {})

    body = response.content.decode()
    rows = list(csv.reader(io.StringIO(body)))
    assert response.status_code == 200
    assert rows[0] == COLUMNS
    assert rows[1][:5] == [str(appointment.pk), "2030-01-07T07:00:00Z", "2030-01-07T07:30:00Z",
                           "BOOKED", "ONLINE"]  # fmt: skip
    assert rows[1][5] == str(clinic.patient.pk) and rows[1][9] == ""
    assert clinic.patient.full_name not in body and clinic.patient.email not in body


def returns_a_never_cached_attachment_with_a_name_when_exported() -> None:
    response = admin_post(admin_client(), EXPORT, {})

    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == 'attachment; filename="appointments-2030-01-07.csv"'
    assert "no-store" in response["Cache-Control"]


def returns_405_to_a_get_so_a_link_cannot_export() -> None:
    assert admin_client().get(EXPORT).status_code == 405


def returns_403_when_the_cross_site_token_is_missing() -> None:
    response = admin_client().post(EXPORT, {}, headers={"Origin": "http://testserver"})

    assert response.status_code == 403
    assert AuditLogEntry.objects.filter(action="appointment.export").count() == 0


def returns_only_the_filtered_set_when_the_list_filters_are_in_the_address() -> None:
    clinic = make_clinic()
    kept = _book(clinic, 1)
    other = _book(clinic, 3, status="COMPLETED")

    rows = _rows(admin_client(), "?status=COMPLETED&=cmd")

    assert [row[0] for row in rows[1:]] == [str(other.pk)]
    assert str(kept.pk) not in [row[0] for row in rows]


def returns_every_row_of_the_set_not_only_a_page_when_exported() -> None:
    clinic = make_clinic()
    for hours in range(1, 26):
        _book(clinic, hours)

    assert len(_rows(admin_client())) == 1 + 25


def returns_an_audit_entry_with_the_row_count_when_exported() -> None:
    clinic = make_clinic()
    _book(clinic, 1)
    _book(clinic, 2)

    _rows(admin_client())

    entry = AuditLogEntry.objects.get(action="appointment.export")
    assert entry.metadata["counts"] == {"row_count": 2}
    assert entry.entity_type == "Appointment"


def returns_a_refusal_and_no_audit_entry_when_the_set_is_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admin_appointment_export, "EXPORT_ROW_LIMIT", 2)
    clinic = make_clinic()
    for hours in (1, 2, 3):
        _book(clinic, hours)

    response = admin_post(admin_client(), EXPORT, {})

    assert response.status_code == 422
    assert "Narrow the days or the filters" in response.content.decode()
    assert AuditLogEntry.objects.filter(action="appointment.export").count() == 0


def returns_an_export_form_not_a_link_on_the_list() -> None:
    html = admin_client().get(LIST, {"status": "BOOKED"}).content.decode()

    opening = 'method="post" action="/admin-console/appointments/export?status=BOOKED"'
    assert opening in html
    assert "csrfmiddlewaretoken" in html
    assert 'href="/admin-console/appointments/export' not in html


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
def returns_403_to_a_patient_and_a_clinician_without_an_audit_entry(role: str) -> None:
    make_user()
    response = admin_post(client_of_role(role), EXPORT, {})

    assert response.status_code == 403
    assert AuditLogEntry.objects.filter(action="appointment.export").count() == 0
