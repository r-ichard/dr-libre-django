"""Task 11, section 14: GET /hospitals/{id}, /providers/{id}, /specialties/{id}. Public, explicit
field lists, and only what search would list."""

import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from scheduling.models import ClinicianProfile
from scheduling.models.builders import add_clinician, make
from scheduling.views import clock
from scheduling.views.pages.search_pages_support import (
    HOUR_OF_SLOTS,
    NOW,
    PLANTED_BIRTH,
    PLANTED_EMAIL,
    PLANTED_PATIENT,
    PLANTED_PHONE,
    PLANTED_REASON,
    plant_clinic,
    update_row,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

PRIVATE_VALUES = (PLANTED_EMAIL, PLANTED_PHONE, PLANTED_BIRTH, PLANTED_PATIENT, PLANTED_REASON)
QUERY_CEILING = 16


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _ids(clinician: ClinicianProfile) -> dict[str, object]:
    return {
        "providers": clinician.pk,
        "hospitals": clinician.department.hospital.pk,
        "specialties": clinician.specialty.pk,
    }


def _get(kind: str, identifier: object) -> "_MonkeyPatchedWSGIResponse":
    return Client().get(f"/api/v1/{kind}/{identifier}")


def returns_provider_with_exactly_the_planned_keys() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(clinician, bio="PLANTED-BIO")

    response = _get("providers", clinician.pk)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {
        "id",
        "full_name",
        "title",
        "bio",
        "specialty",
        "hospital",
        "department",
        "appointment_types",
    }
    assert (body["full_name"], body["bio"]) == ("Ada Lovelace", "PLANTED-BIO")
    assert set(body["hospital"]) == {"id", "name", "city", "time_zone"}
    assert body["hospital"]["time_zone"] == "Europe/Berlin"
    assert set(body["department"]) == {"id", "name"}
    assert [
        (item["id"], item["name"], item["duration_minutes"]) for item in body["appointment_types"]
    ] == [(str(appointment_type.pk), "Check-up", appointment_type.duration_minutes)]


def returns_hospital_with_exactly_the_planned_keys_and_its_public_phone() -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital
    update_row(hospital, phone="+49 777 HOSPITAL-PHONE", description="PLANTED-DESCRIPTION")

    response = _get("hospitals", hospital.pk)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {
        "id",
        "name",
        "description",
        "street_address",
        "postal_code",
        "city",
        "country",
        "phone",
        "time_zone",
        "departments",
        "specialties",
        "providers",
    }
    assert (body["phone"], body["description"]) == ("+49 777 HOSPITAL-PHONE", "PLANTED-DESCRIPTION")
    assert body["time_zone"] == "Europe/Berlin"
    assert [item["name"] for item in body["departments"]] == ["Heart Clinic"]
    assert [item["full_name"] for item in body["providers"]] == ["Ada Lovelace"]
    assert len(body["providers"][0]["next_availabilities"]) == 3


def returns_specialty_with_the_search_body_keys() -> None:
    clinician, _ = plant_clinic()

    response = _get("specialties", clinician.specialty.pk)

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {
        "id",
        "name",
        "provider_count",
        "hospital_count",
        "earliest_availability",
        "has_availability",
    }
    assert (body["provider_count"], body["hospital_count"]) == (1, 1)


@pytest.mark.parametrize("kind", ["providers", "hospitals", "specialties"])
def returns_no_planted_private_value_when_private_columns_are_set(kind: str) -> None:
    clinician, _ = plant_clinic()

    response = _get(kind, _ids(clinician)[kind])

    text = json.dumps(response.json())
    assert response.status_code == 200
    assert [value for value in PRIVATE_VALUES if value in text] == []


@pytest.mark.parametrize("kind", ["providers", "hospitals", "specialties"])
def returns_200_when_no_session_cookie_is_sent(kind: str) -> None:
    clinician, _ = plant_clinic()

    assert _get(kind, _ids(clinician)[kind]).status_code == 200


@pytest.mark.parametrize("kind", ["providers", "hospitals", "specialties"])
def returns_404_with_contract_error_when_id_is_unknown(kind: str) -> None:
    plant_clinic()

    response = _get(kind, uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("kind", ["providers", "hospitals", "specialties"])
def returns_404_when_hospital_is_inactive(kind: str) -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital
    update_row(hospital, is_active=False)

    assert _get(kind, _ids(clinician)[kind]).status_code == 404


@pytest.mark.parametrize("kind", ["providers", "specialties"])
def returns_404_when_specialty_is_inactive(kind: str) -> None:
    clinician, _ = plant_clinic()
    update_row(clinician.specialty, is_active=False)

    assert _get(kind, _ids(clinician)[kind]).status_code == 404


def returns_404_when_provider_is_inactive() -> None:
    clinician, _ = plant_clinic()
    update_row(clinician.user, is_active=False)

    assert _get("providers", clinician.pk).status_code == 404


def returns_404_when_provider_has_no_online_bookable_type() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)

    assert _get("providers", clinician.pk).status_code == 404


def returns_404_when_path_id_is_not_a_uuid() -> None:
    assert Client().get("/api/v1/providers/not-a-uuid").status_code == 404


def returns_same_number_of_queries_when_hospital_has_2_or_12_providers() -> None:
    clinician, _ = plant_clinic()
    hospital_id = clinician.department.hospital.pk
    with CaptureQueriesContext(connection) as few:
        _get("hospitals", hospital_id)
    for number in range(10):
        user = make("User", role="CLINICIAN", full_name=f"Extra Doc {number}")
        add_clinician(clinician.department, HOUR_OF_SLOTS, user=user)

    with CaptureQueriesContext(connection) as many:
        response = _get("hospitals", hospital_id)

    assert len(response.json()["providers"]) == 11
    assert len(many) == len(few)
    assert len(many) <= QUERY_CEILING


def returns_the_slots_search_lists_when_hospital_body_lists_next_availabilities() -> None:
    clinician, _ = plant_clinic()
    searched = Client().get("/api/v1/search/providers").json()["results"][0]

    body = _get("hospitals", clinician.department.hospital.pk).json()

    listed = body["providers"][0]["next_availabilities"]
    assert listed == searched["next_availabilities"]
    assert listed[0]["time_zone"] == "Europe/Berlin"
    assert listed[0]["starts_at"].endswith("Z")
