"""Task 15: the waitlist page as a browser sends it. Each test states the behaviour in words."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db.models import F
from django.test import Client

from scheduling.models import Appointment, User, WaitlistEntry
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, signed_in_patient
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN, browser_post

pytestmark = pytest.mark.django_db

PATH = "/patient/waitlist"
FIRST_DAY = (NOW + timedelta(days=3)).date().isoformat()
LAST_DAY = (NOW + timedelta(days=6)).date().isoformat()


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _form(clinic: Clinic, **overrides: str) -> dict[str, str]:
    base = {
        "appointment_type": str(clinic.appointment_type.pk),
        "provider": "",
        "earliest_day": FIRST_DAY,
        "latest_day": LAST_DAY,
    }
    return {**base, **overrides}


def _offered(clinic: Clinic, patient: User | None = None) -> WaitlistEntry:
    freed = make(
        "Appointment",
        patient=make("User"),
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + timedelta(minutes=30),
        status="CANCELLED",
        cancelled_at=NOW,
        cancellation_reason="Cancelled",
    )
    entry = make(
        "WaitlistEntry",
        patient=patient or clinic.patient,
        appointment_type=clinic.appointment_type,
        earliest_at=STARTS_AT - timedelta(days=1),
        latest_at=STARTS_AT + timedelta(days=1),
        status="OFFERED",
        offered_appointment=freed,
    )
    assert isinstance(entry, WaitlistEntry)
    return entry


def returns_303_and_waiting_entry_when_join_form_is_posted_as_a_browser_sends_it() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, PATH, _form(clinic))

    assert response.status_code == 303
    entry = WaitlistEntry.objects.get(patient=clinic.patient)
    assert entry.status == "WAITING"


def returns_403_when_join_form_comes_from_another_site() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, PATH, _form(clinic), OTHER_SITE_ORIGIN)

    assert response.status_code == 403
    assert not WaitlistEntry.objects.exists()


def returns_422_with_error_summary_when_last_day_is_before_first_day() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(
        client, PATH, _form(clinic, latest_day=FIRST_DAY, earliest_day=LAST_DAY)
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert "There is a problem" in html
    assert 'aria-describedby="id_latest_day_error"' in html
    assert f'value="{LAST_DAY}"' in html


def returns_422_when_no_appointment_type_is_chosen() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, PATH, _form(clinic, appointment_type=""))

    assert response.status_code == 422
    assert not WaitlistEntry.objects.exists()


def returns_422_when_provider_is_not_of_the_chosen_type() -> None:
    clinic = make_clinic()
    other = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, PATH, _form(clinic, provider=str(other.clinician.pk)))

    assert response.status_code == 422
    assert "That provider does not offer this service." in response.content.decode()


def returns_empty_state_and_join_form_when_patient_has_no_entry() -> None:
    clinic = make_clinic()

    html = signed_in_patient(clinic.patient).get(PATH).content.decode()

    assert "You are not on a waitlist" in html
    assert 'name="appointment_type"' in html
    assert no_inline_code(html)


def returns_only_own_entries_in_the_list() -> None:
    clinic = make_clinic()
    make("WaitlistEntry", patient=make("User"), appointment_type=clinic.appointment_type)
    make("WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type)

    html = signed_in_patient(clinic.patient).get(PATH).content.decode()

    assert html.count('class="card waitlist-entry"') == 1
    assert "Waiting" in html


def returns_offer_with_accept_form_when_entry_is_offered() -> None:
    clinic = make_clinic()
    entry = _offered(clinic)

    html = signed_in_patient(clinic.patient).get(PATH).content.decode()

    assert f'action="{PATH}/{entry.pk}/accept"' in html
    assert clinic.clinician.user.full_name in html
    assert "csrfmiddlewaretoken" in html


def returns_303_and_appointment_when_offer_is_accepted() -> None:
    clinic = make_clinic()
    entry = _offered(clinic)
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, f"{PATH}/{entry.pk}/accept", {})

    entry.refresh_from_db()
    assert response.status_code == 303
    assert entry.status == "BOOKED"
    assert Appointment.objects.filter(patient=clinic.patient, status="BOOKED").exists()


def returns_refusal_with_way_forward_when_offered_slot_was_taken() -> None:
    clinic = make_clinic()
    entry = _offered(clinic)
    make(
        "Appointment",
        patient=make("User"),
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT,
        ends_at=STARTS_AT + timedelta(minutes=30),
    )
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, f"{PATH}/{entry.pk}/accept", {})

    html = response.content.decode()
    entry.refresh_from_db()
    assert response.status_code == 409
    assert "That time was just taken." in html
    assert f'href="{PATH}"' in html
    assert entry.status == "OFFERED"


def returns_refusal_when_a_waiting_entry_is_accepted() -> None:
    clinic = make_clinic()
    entry = make("WaitlistEntry", patient=clinic.patient, appointment_type=clinic.appointment_type)
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, f"{PATH}/{entry.pk}/accept", {})

    assert response.status_code == 409
    assert "This offer is no longer open." in response.content.decode()


def returns_403_and_no_provider_name_when_accepting_another_patients_entry() -> None:
    clinic = make_clinic()
    User.objects.filter(pk=clinic.clinician.user_id).update(
        full_name="Planted Provider Name", version=F("version") + 1
    )
    stranger = make("User")
    assert isinstance(stranger, User)
    entry = _offered(clinic, stranger)
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, f"{PATH}/{entry.pk}/accept", {})

    entry.refresh_from_db()
    assert response.status_code == 403
    assert "Planted Provider Name" not in response.content.decode()
    assert entry.status == "OFFERED"


def returns_404_when_accepting_an_unknown_entry() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.patient)

    response = browser_post(client, f"{PATH}/00000000-0000-4000-8000-000000000000/accept", {})

    assert response.status_code == 404


def returns_403_when_a_clinician_opens_the_waitlist() -> None:
    clinic = make_clinic()
    client = signed_in_patient(clinic.clinician.user)

    assert client.get(PATH).status_code == 403


def returns_redirect_to_sign_in_when_visitor_opens_the_waitlist() -> None:
    response = Client().get(PATH)

    assert response.status_code == 302
    assert response["Location"].startswith("/sign-in?next=")
