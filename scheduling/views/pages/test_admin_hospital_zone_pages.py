"""Section 4: saving a hospital with another time zone asks the admin first,
naming the upcoming appointments that would show another local time. Browser-shaped posts."""

from datetime import UTC, datetime, timedelta

import pytest

from scheduling.models import Hospital
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.admin_support import CONSOLE, admin_client, admin_post

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOSPITAL_FORM = {
    "name": "Saint Anne", "code": "Saint-Anne", "street_address": "1 Rue Neuve",
    "postal_code": "75001", "city": "Paris", "country": "France", "phone": "+33 1 23 45 67 89",
    "time_zone": "Europe/Paris", "latitude": "", "longitude": "", "description": "",
    "is_active": "on",
}  # fmt: skip


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


ZONE_SENTENCE = (
    "1 upcoming appointment will show another local time. For example, "
    "Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read "
    "Tuesday 8 January 2030, 19:00 (Pacific/Auckland)."
)
TOKYO_SENTENCE = (
    "1 upcoming appointment will show another local time. For example, "
    "Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read "
    "Tuesday 8 January 2030, 15:00 (Asia/Tokyo)."
)
TWO_SENTENCE = (
    "2 upcoming appointments will show another local time. For example, "
    "Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read "
    "Tuesday 8 January 2030, 19:00 (Pacific/Auckland)."
)


def _zone_form(hospital: Hospital, time_zone: str) -> dict[str, str]:
    return {**HOSPITAL_FORM, "code": hospital.code, "time_zone": time_zone, "version": "1"}


def _book(clinic: Clinic, starts_at: datetime, status: str = "BOOKED") -> None:
    cancellation = {"cancelled_at": NOW, "cancellation_reason": "Patient asked"}
    make(
        "Appointment", patient=clinic.patient, clinician=clinic.clinician,
        appointment_type=clinic.appointment_type, status=status,
        starts_at=starts_at, ends_at=starts_at + timedelta(hours=1),
        **(cancellation if status == "CANCELLED" else {}),
    )  # fmt: skip


def returns_200_with_warning_and_confirm_button_when_zone_changes_with_upcoming() -> None:
    clinic = make_clinic()
    _book(clinic, NOW + timedelta(days=1))
    hospital = clinic.department.hospital

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Pacific/Auckland"),
    )  # fmt: skip

    html = response.content.decode()
    assert response.status_code == 200
    assert ZONE_SENTENCE in html
    assert "Save with the new time zone" in html
    assert 'name="version" value="1"' in html
    assert 'name="confirm_time_zone" value="Pacific/Auckland"' in html
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Europe/Berlin"


def returns_warning_counting_only_future_active_appointments_of_this_hospital() -> None:
    clinic = make_clinic()
    hospital = clinic.department.hospital
    _book(clinic, NOW + timedelta(days=1))
    _book(clinic, NOW - timedelta(days=1))
    _book(clinic, NOW + timedelta(days=3), status="CANCELLED")
    _book(make_clinic(), NOW + timedelta(days=2))

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Pacific/Auckland"),
    )  # fmt: skip

    assert response.status_code == 200
    assert ZONE_SENTENCE in response.content.decode()


def returns_plural_warning_with_the_earliest_start_as_example_when_two_are_upcoming() -> None:
    clinic = make_clinic()
    _book(clinic, NOW + timedelta(days=2))
    _book(clinic, NOW + timedelta(days=1))
    hospital = clinic.department.hospital

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Pacific/Auckland"),
    )  # fmt: skip

    assert response.status_code == 200
    assert TWO_SENTENCE in response.content.decode()


def returns_303_without_warning_when_the_only_appointment_starts_exactly_now() -> None:
    clinic = make_clinic()
    _book(clinic, NOW)
    hospital = clinic.department.hospital

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Pacific/Auckland"),
    )  # fmt: skip

    assert response.status_code == 303
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Pacific/Auckland"


def returns_303_and_stores_the_new_zone_when_time_zone_change_is_confirmed() -> None:
    clinic = make_clinic()
    _book(clinic, NOW + timedelta(days=1))
    hospital = clinic.department.hospital
    data = {
        **_zone_form(hospital, "Pacific/Auckland"),
        "confirm_time_zone": "Pacific/Auckland",
    }

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit", data)

    assert response.status_code == 303
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Pacific/Auckland"


def returns_200_with_new_warning_and_no_save_when_zone_changes_after_the_warning() -> None:
    clinic = make_clinic()
    _book(clinic, NOW + timedelta(days=1))
    hospital = clinic.department.hospital
    data = {
        **_zone_form(hospital, "Asia/Tokyo"),
        "confirm_time_zone": "Pacific/Auckland",
    }

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit", data)

    html = response.content.decode()
    assert response.status_code == 200
    assert TOKYO_SENTENCE in html
    assert 'name="confirm_time_zone" value="Asia/Tokyo"' in html
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Europe/Berlin"


def returns_303_without_warning_when_no_upcoming_local_time_changes() -> None:
    clinic = make_clinic()
    _book(clinic, NOW + timedelta(days=1))
    hospital = clinic.department.hospital

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Europe/Paris"),
    )  # fmt: skip

    assert response.status_code == 303
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Europe/Paris"


def returns_303_without_warning_when_only_past_or_cancelled_appointments_would_shift() -> None:
    clinic = make_clinic()
    hospital = clinic.department.hospital
    _book(clinic, NOW - timedelta(days=1))
    _book(clinic, NOW + timedelta(days=3), status="CANCELLED")

    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit",
        _zone_form(hospital, "Pacific/Auckland"),
    )  # fmt: skip

    assert response.status_code == 303
    assert Hospital.objects.get(pk=hospital.pk).time_zone == "Pacific/Auckland"
