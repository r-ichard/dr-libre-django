"""Section 10: the admin waitlist as a browser uses it. Routes:
/admin-console/waitlist[/new|/<id>/offer|/<id>/accept]."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db.models import F

from scheduling.models import Appointment, WaitlistEntry
from scheduling.models.builders import make_clinic, make_user
from scheduling.use_cases.test_waitlist_support import (
    SLOT,
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LIST = "/admin-console/waitlist"


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_entries_oldest_first_filtered_by_status_when_the_list_is_opened() -> None:
    clinic = make_clinic()
    older = _entry_for(clinic, patient=make_user(full_name="Older Person"))
    newer = _entry_for(clinic, patient=make_user(full_name="Newer Person"))
    WaitlistEntry.objects.filter(pk=older.pk).update(
        created_at=NOW - timedelta(days=2), version=F("version") + 1
    )
    WaitlistEntry.objects.filter(pk=newer.pk).update(
        created_at=NOW - timedelta(days=1), version=F("version") + 1
    )
    _entry_for(clinic, status="EXPIRED", patient=make_user(full_name="Expired Person"))

    html = admin_client().get(f"{LIST}?status=WAITING").content.decode()

    assert "Older Person" in html and "Newer Person" in html
    assert html.index("Older Person") < html.index("Newer Person")
    assert "Expired Person" not in html


def returns_the_offered_slot_in_the_hospital_zone_when_an_entry_is_offered() -> None:
    clinic = make_clinic()
    _offered_entry(clinic, _cancelled_slot(clinic))

    html = admin_client().get(LIST).content.decode()

    assert "11:00" in html and "Europe/Berlin" in html


def returns_every_error_in_one_answer_when_the_add_form_is_empty() -> None:
    response = admin_post(admin_client(), f"{LIST}/new", {})

    html = response.content.decode()
    assert response.status_code == 422
    assert html.count('<li><a href="#') >= 2
    assert WaitlistEntry.objects.count() == 0


def returns_303_and_a_waiting_entry_when_an_admin_adds_a_patient() -> None:
    clinic = make_clinic()
    values = {
        "patient": str(clinic.patient.pk),
        "appointment_type": str(clinic.appointment_type.pk),
        "preferred_clinician": "",
        "earliest_at": "2030-01-06T09:00",
        "latest_at": "2030-01-08T09:00",
    }

    response = admin_post(admin_client(), f"{LIST}/new", values)

    assert response.status_code == 303
    assert WaitlistEntry.objects.get().status == "WAITING"


def returns_422_and_the_accepted_years_when_latest_is_after_2099() -> None:
    clinic = make_clinic()
    values = {
        "patient": str(clinic.patient.pk),
        "appointment_type": str(clinic.appointment_type.pk),
        "preferred_clinician": "",
        "earliest_at": "2030-05-01T09:00",
        "latest_at": "2130-05-01T09:00",
    }

    response = admin_post(admin_client(), f"{LIST}/new", values)

    html = response.content.decode()
    assert response.status_code == 422
    assert "Enter a date and a time between 2000 and 2099." in html
    assert WaitlistEntry.objects.count() == 0


def returns_the_offered_entry_when_an_admin_offers_a_waiting_entry() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    response = admin_post(admin_client(), f"{LIST}/{entry.pk}/offer", {})

    entry.refresh_from_db()
    assert response.status_code == 303
    assert (entry.status, entry.offered_appointment_id) == ("OFFERED", freed.pk)


def returns_the_reason_and_a_link_back_when_no_cancelled_time_fits() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)

    response = admin_post(admin_client(), f"{LIST}/{entry.pk}/offer", {})

    html = response.content.decode()
    assert response.status_code == 409
    assert "No cancelled time of this type falls inside the window." in html
    assert f'href="{LIST}' in html


def returns_a_booked_entry_and_an_appointment_when_an_admin_accepts_for_the_patient() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _offered_entry(clinic, freed)

    response = admin_post(admin_client(), f"{LIST}/{entry.pk}/accept", {})

    entry.refresh_from_db()
    assert response.status_code == 303 and entry.status == "BOOKED"
    placed = Appointment.objects.get(waitlist_entry=entry)
    assert (placed.patient_id, placed.starts_at) == (clinic.patient.pk, SLOT)


def returns_405_when_the_offer_route_is_opened_with_get() -> None:
    entry = _entry_for(make_clinic())

    assert admin_client().get(f"{LIST}/{entry.pk}/offer").status_code == 405
