"""Section 14 GET and POST /appointments: scoped list, booking, the failure contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.test import Client

from scheduling.models import Appointment, User
from scheduling.models.builders import STARTS_AT, add_clinician, make, make_clinic
from scheduling.views import clock
from scheduling.views.test_appointment_support import (
    APPOINTMENTS,
    NOW,
    THIRTY_MINUTES,
    _admin,
    _make_appointment,
    _signed_in,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

FOREIGN_ORIGIN = "https://evil.example"
PLANTED_VISIT_REASON = "planted-visit-reason-5521"
OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _book(
    client: Client, body: Mapping[str, object], origin: str = ""
) -> _MonkeyPatchedWSGIResponse:
    headers = {"Origin": origin} if origin else {}
    return client.post(APPOINTMENTS, body, content_type="application/json", headers=headers)


def _ids(response: _MonkeyPatchedWSGIResponse) -> list[str]:
    return [item["id"] for item in response.json()["results"]]


def returns_401_when_listing_without_session() -> None:
    response = Client().get(APPOINTMENTS)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def returns_401_when_booking_without_session() -> None:
    response = _book(Client(), {})

    assert response.status_code == 401


def returns_only_own_when_patient_lists() -> None:
    clinic = make_clinic()
    own = _make_appointment(clinic)
    _make_appointment(clinic, patient=make("User"), clinician=add_clinician(clinic.department))

    response = _signed_in(clinic.patient).get(APPOINTMENTS)

    assert _ids(response) == [str(own.pk)]
    assert response.json()["count"] == 1


def returns_empty_page_when_patient_filters_by_other_patient() -> None:
    clinic = make_clinic()
    stranger = make("User")
    _make_appointment(clinic, patient=stranger)

    response = _signed_in(clinic.patient).get(f"{APPOINTMENTS}?patient_id={stranger.pk}")

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["count"] == 0


def returns_only_own_calendar_when_clinician_lists() -> None:
    clinic = make_clinic()
    mine = _make_appointment(clinic)
    _make_appointment(clinic, clinician=add_clinician(clinic.department), patient=make("User"))
    user = clinic.clinician.user
    assert isinstance(user, User)
    user.refresh_from_db()  # the stored version moved on after the clinician row was built

    response = _signed_in(user).get(APPOINTMENTS)

    assert _ids(response) == [str(mine.pk)]


def returns_all_when_admin_lists() -> None:
    clinic = make_clinic()
    first = _make_appointment(clinic)
    second = _make_appointment(
        clinic, clinician=add_clinician(clinic.department), patient=make("User")
    )

    response = _signed_in(_admin()).get(APPOINTMENTS)

    assert sorted(_ids(response)) == sorted([str(first.pk), str(second.pk)])


def returns_page_of_20_with_count_when_25_exist() -> None:
    clinic = make_clinic()
    for day in range(25):
        start = STARTS_AT + timedelta(days=day)
        _make_appointment(clinic, starts_at=start, ends_at=start + THIRTY_MINUTES)
    client = _signed_in(clinic.patient)

    first = client.get(APPOINTMENTS).json()
    second = client.get(f"{APPOINTMENTS}?page=2").json()

    assert (first["count"], first["page"], first["page_size"], len(first["results"])) == (
        25,
        1,
        20,
        20,
    )
    assert (second["page"], len(second["results"])) == (2, 5)


def returns_only_matching_status_when_filtered_by_status() -> None:
    clinic = make_clinic()
    _make_appointment(clinic)
    later = STARTS_AT + timedelta(days=1)
    done = _make_appointment(
        clinic, starts_at=later, ends_at=later + THIRTY_MINUTES, status="COMPLETED"
    )

    response = _signed_in(clinic.patient).get(f"{APPOINTMENTS}?status=COMPLETED")

    assert _ids(response) == [str(done.pk)]


def returns_only_appointments_inside_range_when_filtered_by_range() -> None:
    clinic = make_clinic()
    _make_appointment(clinic)
    later = STARTS_AT + timedelta(days=3)
    inside = _make_appointment(clinic, starts_at=later, ends_at=later + THIRTY_MINUTES)

    response = _signed_in(clinic.patient).get(
        f"{APPOINTMENTS}?from=2030-01-10T00:00:00Z&to=2030-01-11T00:00:00Z"
    )

    assert _ids(response) == [str(inside.pk)]


def returns_utc_times_with_zone_and_no_free_text_when_listing() -> None:
    clinic = make_clinic()
    appointment = _make_appointment(clinic, patient_reason="private")
    make("ClinicalNote", appointment=appointment, clinical_notes="private")

    item = _signed_in(clinic.patient).get(APPOINTMENTS).json()["results"][0]

    assert item["starts_at"] == "2030-01-07T10:00:00Z"
    assert item["ends_at"] == "2030-01-07T10:30:00Z"
    assert item["time_zone"] == "Europe/Berlin"
    assert "patient_reason" not in item
    assert "clinical_notes" not in item


def returns_201_with_end_from_type_when_patient_books() -> None:
    clinic = make_clinic(type_fields={"duration_minutes": 45})
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 201
    created = response.json()
    assert created["starts_at"] == "2030-01-07T10:00:00Z"
    assert created["ends_at"] == "2030-01-07T10:45:00Z"
    assert (created["status"], created["source"]) == ("BOOKED", "ONLINE")
    assert created["patient_id"] == str(clinic.patient.pk)


def returns_201_round_robin_when_patient_names_no_clinician() -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 201
    assert response.json()["source"] == "ROUND_ROBIN"


def returns_403_when_patient_names_patient() -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "patient_id": str(make("User").pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert Appointment.objects.count() == 0


@pytest.mark.parametrize("extra", [{"ends_at": "2030-01-07T23:00:00Z"}, {"status": "COMPLETED"}])
def returns_400_when_body_has_a_field_the_schema_does_not_know(extra: dict[str, str]) -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
        **extra,
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
    assert Appointment.objects.count() == 0


def returns_400_when_starts_at_has_no_offset() -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 400


def returns_409_conflict_with_resources_list_when_clinician_is_busy() -> None:
    clinic = make_clinic()
    _make_appointment(clinic, patient=make("User"))
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["details"]["resources"] == ["clinician"]


def returns_422_rule_violation_when_type_is_not_bookable_online() -> None:
    clinic = make_clinic(type_fields={"is_bookable_online": False})
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "rule_violation"
    assert error["details"]["violated_rules"] == ["type_not_bookable_online"]


def returns_409_no_clinician_available_when_nobody_is_free() -> None:
    clinic = make_clinic()
    _make_appointment(clinic, patient=make("User"))
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_clinician_available"


def returns_403_when_booking_origin_is_foreign() -> None:
    clinic = make_clinic()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": "2030-01-07T10:00:00Z",
    }

    response = _book(_signed_in(clinic.patient), body, origin=FOREIGN_ORIGIN)

    assert response.status_code == 403
    assert Appointment.objects.count() == 0
