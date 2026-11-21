"""Section 14 GET /slots: public, strict query, UTC times with the hospital time zone beside."""

from datetime import UTC, datetime, time

import pytest
from django.test import Client

from scheduling.models.builders import add_clinician, make_clinic
from scheduling.views import clock

pytestmark = pytest.mark.django_db

SLOTS = "/api/v1/slots"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
MONDAY = "from=2030-01-07T00:00:00Z&to=2030-01-08T00:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_200_without_session_when_visitor_asks_for_slots() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)

    response = Client().get(f"{SLOTS}?appointment_type_id={clinic.appointment_type.pk}&{MONDAY}")

    assert response.status_code == 200


def returns_utc_z_times_with_hospital_zone_named() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    type_id, clinician_id = clinic.appointment_type.pk, clinic.clinician.pk
    query = f"appointment_type_id={type_id}&clinician_id={clinician_id}&{MONDAY}"

    response = Client().get(f"{SLOTS}?{query}")

    assert response.json() == {
        "time_zone": "Europe/Berlin",
        "slots": [
            {
                "starts_at": "2030-01-07T10:00:00Z",
                "ends_at": "2030-01-07T10:30:00Z",
                "clinician_ids": [str(clinic.clinician.pk)],
            },
            {
                "starts_at": "2030-01-07T10:30:00Z",
                "ends_at": "2030-01-07T11:00:00Z",
                "clinician_ids": [str(clinic.clinician.pk)],
            },
        ],
    }


def returns_400_invalid_input_naming_to_when_range_over_31_days() -> None:
    clinic = make_clinic()
    window = "from=2030-01-07T00:00:00Z&to=2030-02-08T00:00:00Z"
    query = f"appointment_type_id={clinic.appointment_type.pk}&{window}"

    response = Client().get(f"{SLOTS}?{query}")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert [item["field"] for item in error["details"]["fields"]] == ["to"]


def returns_400_when_time_has_no_offset() -> None:
    clinic = make_clinic()
    window = "from=2030-01-07T00:00:00&to=2030-01-08T00:00:00Z"
    query = f"appointment_type_id={clinic.appointment_type.pk}&{window}"

    response = Client().get(f"{SLOTS}?{query}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"


def returns_400_when_query_has_unknown_parameter() -> None:
    clinic = make_clinic()
    query = f"appointment_type_id={clinic.appointment_type.pk}&{MONDAY}&patient_id=anyone"

    response = Client().get(f"{SLOTS}?{query}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"


def returns_400_when_appointment_type_is_missing() -> None:
    response = Client().get(f"{SLOTS}?{MONDAY}")

    assert response.status_code == 400


def returns_404_not_found_when_type_is_inactive() -> None:
    clinic = make_clinic(type_fields={"is_active": False})

    response = Client().get(f"{SLOTS}?appointment_type_id={clinic.appointment_type.pk}&{MONDAY}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def returns_only_the_named_clinician_when_the_query_names_one() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    add_clinician(clinic.department, HOUR_OF_SLOTS)
    query = f"appointment_type_id={clinic.appointment_type.pk}&clinician_id={clinic.clinician.pk}"

    slots = Client().get(f"{SLOTS}?{query}&{MONDAY}").json()["slots"]

    assert {identifier for slot in slots for identifier in slot["clinician_ids"]} == {
        str(clinic.clinician.pk)
    }


@pytest.mark.parametrize(
    "window",
    [
        "from=2030-01-07T00:00:00Z&to=2030-01-07T00:00:00Z",
        "from=2030-01-08T00:00:00Z&to=2030-01-07T00:00:00Z",
    ],
)
def returns_400_invalid_input_naming_to_when_slots_to_is_not_after_from(window: str) -> None:
    clinic = make_clinic()

    response = Client().get(f"{SLOTS}?appointment_type_id={clinic.appointment_type.pk}&{window}")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert [item["field"] for item in error["details"]["fields"]] == ["to"]
