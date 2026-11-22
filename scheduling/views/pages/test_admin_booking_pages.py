"""Task 20, items 3 to 5: an admin books for a patient and reschedules, as a browser sends it."""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest

from scheduling.models import Appointment
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post, client_of_role

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
BOOK = "/admin-console/appointments/new"
LIST = "/admin-console/appointments"
MONDAY_SLOT = "2030-01-14T09:00:00Z"
OTHER_SLOT = "2030-01-14T10:00:00Z"
WEEK = "2030-01-14"


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _review(clinic: Clinic, slot: str = MONDAY_SLOT) -> str:
    return (
        f"{BOOK}/{clinic.appointment_type.pk}/review"
        f"?patient={clinic.patient.pk}&provider={clinic.clinician.pk}"
        f"&starts_at={quote(slot, safe=':')}"
    )


def returns_the_patient_by_name_or_email_and_nobody_without_a_query_when_searching() -> None:
    make("User", full_name="Findable Person", email="findable@example.org")
    client = admin_client()

    by_name = client.get(f"{BOOK}?q=Findable").content.decode()
    by_email = client.get(f"{BOOK}?q=findable@example").content.decode()
    nothing = client.get(BOOK).content.decode()

    assert "Findable Person" in by_name and "Findable Person" in by_email
    assert "Findable Person" not in nothing


def returns_every_type_and_no_first_available_when_the_steps_are_followed() -> None:
    clinic = make_clinic({"is_bookable_online": False})
    client = admin_client()

    services = client.get(f"{BOOK}/service?patient={clinic.patient.pk}").content.decode()
    providers = client.get(
        f"{BOOK}/{clinic.appointment_type.pk}/provider?patient={clinic.patient.pk}"
    ).content.decode()

    assert clinic.appointment_type.name in services and "not bookable online" in services
    assert "First available" not in providers
    assert clinic.clinician.user.full_name in providers


def returns_the_week_of_times_when_the_provider_is_chosen() -> None:
    clinic = make_clinic({"is_bookable_online": False})
    address = (
        f"{BOOK}/{clinic.appointment_type.pk}/times"
        f"?patient={clinic.patient.pk}&provider={clinic.clinician.pk}&week={WEEK}"
    )

    html = admin_client().get(address).content.decode()

    assert "/review?" in html and f"patient={clinic.patient.pk}" in html


def returns_a_staff_appointment_when_the_admin_confirms_the_review() -> None:
    clinic = make_clinic({"is_bookable_online": False})

    response = admin_post(admin_client(), _review(clinic), {})

    placed = Appointment.objects.get(patient=clinic.patient)
    assert response.status_code == 303 and placed.source == "STAFF"
    assert response["Location"] == f"{LIST}/{placed.pk}"


def returns_the_conflict_and_a_link_to_the_times_when_the_slot_is_taken() -> None:
    clinic = make_clinic()
    start = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
    make(
        "Appointment", clinician=clinic.clinician, appointment_type=clinic.appointment_type,
        starts_at=start, ends_at=start + timedelta(minutes=30),
    )  # fmt: skip

    response = admin_post(admin_client(), _review(clinic), {})

    html = response.content.decode()
    assert response.status_code == 409 and "no longer free" in html
    assert f"{BOOK}/{clinic.appointment_type.pk}/times" in html


def returns_the_search_step_when_the_patient_in_the_address_is_not_a_patient() -> None:
    clinic = make_clinic()
    staff = make("User", role="CLINICIAN")

    response = admin_client().get(f"{BOOK}/service?patient={staff.pk}")

    assert response.status_code == 302 and response["Location"] == BOOK
    assert clinic.patient.pk != staff.pk


def returns_403_when_a_clinician_posts_a_booking() -> None:
    clinic = make_clinic()

    response = admin_post(client_of_role("CLINICIAN"), _review(clinic), {})

    assert response.status_code == 403 and not Appointment.objects.exists()


def returns_the_new_time_when_an_admin_reschedules_a_booked_appointment() -> None:
    clinic = make_clinic()
    start = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
    appointment = make(
        "Appointment", clinician=clinic.clinician, appointment_type=clinic.appointment_type,
        starts_at=start, ends_at=start + timedelta(minutes=30),
    )  # fmt: skip
    assert isinstance(appointment, Appointment)
    base = f"{LIST}/{appointment.pk}/reschedule"
    client = admin_client()

    times = client.get(f"{base}?week={WEEK}").content.decode()
    moved = admin_post(client, f"{base}/review?starts_at={OTHER_SLOT}", {})

    appointment.refresh_from_db()
    assert "/review?starts_at=" in times
    assert moved.status_code == 303 and appointment.starts_at == datetime(
        2030, 1, 14, 10, 0, tzinfo=UTC
    )


def returns_409_and_the_way_back_when_a_cancelled_appointment_is_rescheduled() -> None:
    appointment = make(
        "Appointment", status="CANCELLED", cancelled_at=NOW, cancellation_reason="Moved away"
    )
    assert isinstance(appointment, Appointment)

    response = admin_client().get(f"{LIST}/{appointment.pk}/reschedule")

    assert response.status_code == 409
    assert f"{LIST}/{appointment.pk}" in response.content.decode()


def returns_422_and_the_not_offered_sentence_when_admin_reschedules_off_the_grid() -> None:
    clinic = make_clinic()
    start = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
    appointment = make(
        "Appointment", clinician=clinic.clinician, appointment_type=clinic.appointment_type,
        starts_at=start, ends_at=start + timedelta(minutes=30),
    )  # fmt: skip

    response = admin_post(
        admin_client(),
        f"{LIST}/{appointment.pk}/reschedule/review?starts_at=2030-01-14T01:00:00Z",
        {},
    )

    body = response.content.decode()
    assert response.status_code == 422
    assert "That time is not offered. Choose one from the week." in body
    assert "outside_availability" not in body


def returns_409_and_the_cancelled_sentence_when_rescheduled_by_post() -> None:
    appointment = make(
        "Appointment", status="CANCELLED", cancelled_at=NOW, cancellation_reason="Moved away"
    )
    assert isinstance(appointment, Appointment)

    response = admin_post(
        admin_client(), f"{LIST}/{appointment.pk}/reschedule/review?starts_at={OTHER_SLOT}", {}
    )

    assert response.status_code == 409
    assert (
        "This appointment is cancelled, so it cannot be rescheduled." in response.content.decode()
    )
