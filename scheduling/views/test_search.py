"""Section 14 GET /search/*: public, explicit fields only, UTC times with the zone named."""

import json
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING

import pytest

from scheduling.models.builders import add_clinician, make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
KINDS = ["providers", "hospitals", "specialties"]
PLANTED = {
    "email": "planted.clinician@example.org",
    "phone": "+49 555 PLANTED-PHONE",
    "birth": "1971-02-03",
    "bio": "PLANTED-BIO-TEXT",
    "hospital_phone": "+49 777 PLANTED-HOSPITAL",
    "hospital_description": "PLANTED-HOSPITAL-DESCRIPTION",
}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _publish_one_clinician() -> object:
    hospital = make(
        "Hospital",
        name="Riverside General",
        phone=PLANTED["hospital_phone"],
        description=PLANTED["hospital_description"],
        latitude=52.5,
        longitude=13.4,
    )
    department = make("Department", hospital=hospital)
    make("AppointmentType", department=department)
    user = make(
        "User",
        role="CLINICIAN",
        full_name="Ada Lovelace",
        email=PLANTED["email"],
        phone=PLANTED["phone"],
        date_of_birth=datetime.fromisoformat(PLANTED["birth"]).date(),
    )
    return add_clinician(department, HOUR_OF_SLOTS, user=user, bio=PLANTED["bio"])


def _get(kind: str, query: str = "") -> "_MonkeyPatchedWSGIResponse":
    return browser_api_client().get(f"/api/v1/search/{kind}?{query}")


@pytest.mark.parametrize("kind", KINDS)
def returns_200_without_a_session_for_each_endpoint(kind: str) -> None:
    _publish_one_clinician()

    response = browser_api_client().get(f"/api/v1/search/{kind}")

    assert response.status_code == 200


@pytest.mark.parametrize("kind", KINDS)
def returns_200_when_the_session_cookie_is_garbage(kind: str) -> None:
    client = browser_api_client()
    client.cookies["drlibre_session"] = "garbage"

    assert client.get(f"/api/v1/search/{kind}").status_code == 200


def returns_the_envelope_with_total_page_and_page_count() -> None:
    _publish_one_clinician()

    body = _get("providers").json()

    assert {key: body[key] for key in ("total", "page", "page_count", "page_size")} == {
        "total": 1,
        "page": 1,
        "page_count": 1,
        "page_size": 20,
    }
    assert set(body) == {"results", "total", "page", "page_count", "page_size"}


def returns_provider_with_exactly_the_planned_keys() -> None:
    _publish_one_clinician()

    result = _get("providers").json()["results"][0]

    assert set(result) == {
        "id",
        "full_name",
        "title",
        "specialty",
        "hospital",
        "department",
        "appointment_type",
        "next_availabilities",
        "has_availability",
    }
    assert set(result["hospital"]) == {"id", "name", "city", "time_zone"}
    assert set(result["next_availabilities"][0]) == {
        "starts_at",
        "clinician_id",
        "appointment_type_id",
        "time_zone",
    }


def returns_hospital_with_exactly_the_planned_keys() -> None:
    _publish_one_clinician()

    assert set(_get("hospitals").json()["results"][0]) == {
        "id",
        "name",
        "street_address",
        "postal_code",
        "city",
        "country",
        "time_zone",
        "specialties",
        "bookable_provider_count",
        "earliest_availability",
        "providers_with_availability_count",
        "has_availability",
    }


def returns_specialty_with_exactly_the_planned_keys() -> None:
    _publish_one_clinician()

    assert set(_get("specialties").json()["results"][0]) == {
        "id",
        "name",
        "provider_count",
        "hospital_count",
        "earliest_availability",
        "has_availability",
    }


@pytest.mark.parametrize("kind", KINDS)
def returns_contains_no_planted_value_when_private_columns_are_set(kind: str) -> None:
    _publish_one_clinician()

    body = _get(kind).json()
    assert body["total"] == 1
    text = json.dumps(body)

    leaked = [label for label, value in PLANTED.items() if value in text]
    assert leaked == []
    assert "52.5" not in text


def returns_utc_z_times_with_hospital_zone_named_on_each_slot() -> None:
    _publish_one_clinician()

    slots = _get("providers").json()["results"][0]["next_availabilities"]

    assert [(slot["starts_at"], slot["time_zone"]) for slot in slots] == [
        ("2030-01-07T10:00:00Z", "Europe/Berlin"),
        ("2030-01-07T10:30:00Z", "Europe/Berlin"),
        ("2030-01-14T10:00:00Z", "Europe/Berlin"),
    ]


def returns_the_earliest_availability_as_a_slot_on_a_hospital() -> None:
    _publish_one_clinician()

    earliest = _get("hospitals").json()["results"][0]["earliest_availability"]

    assert (earliest["starts_at"], earliest["time_zone"]) == (
        "2030-01-07T10:00:00Z",
        "Europe/Berlin",
    )


def returns_null_earliest_availability_when_nothing_is_free() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    add_clinician(department, {"valid_from": datetime(2031, 1, 1).date()})

    result = _get("specialties").json()["results"][0]

    assert (result["earliest_availability"], result["has_availability"]) == (None, False)


def returns_defaults_when_page_size_is_bogus() -> None:
    _publish_one_clinician()

    body = _get("providers", "page_size=1000&page=abc&sort=sideways&window=never&from=soon").json()

    assert (body["page_size"], body["page"], body["total"]) == (20, 1, 1)


def returns_last_page_when_page_is_past_the_end() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    for number in range(12):
        add_clinician(
            department,
            HOUR_OF_SLOTS,
            user=make("User", role="CLINICIAN", full_name=f"Doc {number:02d}"),
        )

    body = _get("providers", "page_size=10&page=99&sort=name_asc").json()

    assert (body["page"], body["page_count"], len(body["results"])) == (2, 2, 2)


def returns_matching_results_when_text_is_partial_and_upper_case() -> None:
    _publish_one_clinician()

    assert _get("providers", "q=LOVEL").json()["total"] == 1
    assert _get("providers", "q=zebra").json()["total"] == 0


def returns_404_contract_error_for_unknown_search_path() -> None:
    response = browser_api_client().get("/api/v1/search/nurses")

    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")


def returns_the_hospital_zone_in_the_provider_hospital_block() -> None:
    _publish_one_clinician()

    hospital = _get("providers").json()["results"][0]["hospital"]

    assert hospital["time_zone"] == "Europe/Berlin"
