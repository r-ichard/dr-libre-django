"""Section 6: a caller with no session, and a patient, see only what public search shows.
Staff keep the types that are not bookable online (section 10, "Book for a patient")."""

from datetime import UTC, datetime, time

import pytest

from scheduling.models.builders import Clinic, change_and_save, make_clinic
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.pages.booking_pages_support import details_path, times_path
from scheduling.views.pages.browser_support import browser_client
from scheduling.views.test_appointment_support import _admin, _signed_in

pytestmark = pytest.mark.django_db

SLOTS = "/api/v1/slots"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
# 08:00 to 10:00 Berlin is 07:00 to 09:00 UTC: the 07:00 and 07:30 starts fall inside
# the 120 minute lead time from 06:00 UTC; 08:00 is exactly at its edge and stays offered.
LEAD_TIME_RULE = {"start_time": time(8, 0), "end_time": time(10, 0), "slot_step_minutes": 30}
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
MONDAY = "from=2030-01-07T00:00:00Z&to=2030-01-08T00:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _in_person_only_clinic() -> Clinic:
    return make_clinic(type_fields={"is_bookable_online": False}, rule_fields=HOUR_OF_SLOTS)


def _slots_path(clinic: Clinic) -> str:
    return f"{SLOTS}?appointment_type_id={clinic.appointment_type.pk}&{MONDAY}"


def returns_404_when_slots_ask_for_a_type_not_bookable_online() -> None:
    clinic = _in_person_only_clinic()

    response = browser_api_client().get(_slots_path(clinic))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def returns_404_when_patient_asks_slots_for_a_type_not_bookable_online() -> None:
    clinic = _in_person_only_clinic()

    response = _signed_in(clinic.patient).get(_slots_path(clinic))

    assert response.status_code == 404


def returns_slots_when_admin_asks_for_a_type_not_bookable_online() -> None:
    clinic = _in_person_only_clinic()

    response = _signed_in(_admin()).get(_slots_path(clinic))

    assert response.status_code == 200
    assert len(response.json()["slots"]) == 2


def returns_404_when_slots_name_a_clinician_with_inactive_specialty() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    change_and_save(clinic.clinician.specialty, "is_active", False)
    query = f"appointment_type_id={clinic.appointment_type.pk}&clinician_id={clinic.clinician.pk}"

    response = browser_api_client().get(f"{SLOTS}?{query}&{MONDAY}")

    assert response.status_code == 404


def returns_404_when_booking_page_gets_a_type_not_bookable_online() -> None:
    clinic = _in_person_only_clinic()

    response = browser_client().get(times_path(clinic))

    assert response.status_code == 404


def returns_404_when_details_page_gets_a_type_not_bookable_online() -> None:
    clinic = _in_person_only_clinic()

    response = browser_client().get(details_path(clinic))

    assert response.status_code == 404
    assert "<form" not in response.content.decode().split("<main", 1)[-1]


def returns_404_when_booking_page_names_a_clinician_with_inactive_specialty() -> None:
    clinic = make_clinic()
    change_and_save(clinic.clinician.specialty, "is_active", False)

    response = browser_client().get(details_path(clinic))

    assert response.status_code == 404


def returns_form_when_visitor_opens_details_of_a_bookable_type() -> None:
    clinic = make_clinic()

    response = browser_client().get(details_path(clinic))

    assert response.status_code == 200


def _booking_of(clinic: Clinic) -> dict[str, str]:
    return {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "patient_id": str(clinic.patient.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }


def returns_404_when_patient_books_a_clinician_the_public_search_hides() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    change_and_save(clinic.clinician.specialty, "is_active", False)

    response = _signed_in(clinic.patient).post(
        "/api/v1/appointments", _booking_of(clinic), content_type="application/json"
    )

    assert response.status_code == 404


def returns_201_when_admin_books_a_clinician_the_public_search_hides() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    change_and_save(clinic.clinician.specialty, "is_active", False)

    response = _signed_in(_admin()).post(
        "/api/v1/appointments", _booking_of(clinic), content_type="application/json"
    )

    assert response.status_code == 201


def returns_no_slot_inside_lead_time_for_a_visitor() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)

    response = browser_api_client().get(_slots_path(clinic))

    starts = [slot["starts_at"] for slot in response.json()["slots"]]
    assert starts == ["2030-01-07T08:00:00Z", "2030-01-07T08:30:00Z"]
