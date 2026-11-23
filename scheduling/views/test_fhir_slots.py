"""Sections 15.2, 15.5, 15.6: Slot is computed by the use case, never stored. A start
range of 31 days at most is required; busy statuses are for staff; the id reads a slot back."""

from datetime import UTC, datetime, time, timedelta

import pytest

from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, client_for, get, token_of
from scheduling.views.pages.search_pages_support import update_row

pytestmark = pytest.mark.django_db

# 08:00 to 10:00 Berlin is 07:00 to 09:00 UTC: the 07:00 and 07:30 starts fall inside
# the 120 minute lead time from 06:00 UTC; 08:00 is exactly at its edge and stays offered.
LEAD_TIME_RULE = {"start_time": time(8, 0), "end_time": time(10, 0), "slot_step_minutes": 30}
HOURS = {"start_time": time(11, 0), "end_time": time(13, 0), "slot_step_minutes": 30}
MONDAY = "start=ge2030-01-07T00:00:00Z&start=lt2030-01-08T00:00:00Z"
FIRST = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
HALF_HOUR = timedelta(minutes=30)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _search(clinic: object, extra: str = "", token: str | None = None) -> list[dict[str, object]]:
    path = f"/fhir/Slot?service-type={clinic.appointment_type.pk}&{MONDAY}{extra}"  # type: ignore[attr-defined]
    response = get(path, token)
    assert response.status_code == 200
    return [item["resource"] for item in response.json().get("entry", [])]


def returns_the_slots_the_application_api_offers_when_same_type_clinician_and_range() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    type_id, clinician_id = clinic.appointment_type.pk, clinic.clinician.pk
    api = client_for(None).get(
        f"/api/v1/slots?appointment_type_id={type_id}&clinician_id={clinician_id}"
        "&from=2030-01-07T00:00:00Z&to=2030-01-08T00:00:00Z"
    )

    fhir = _search(clinic, f"&schedule.actor=Practitioner/{clinic.clinician.user_id}")

    assert [slot["start"] for slot in fhir] == [item["starts_at"] for item in api.json()["slots"]]
    assert [slot["status"] for slot in fhir] == ["free"] * 4


@pytest.mark.parametrize(
    ("query", "named"),
    [
        ("", "start"),
        ("start=ge2030-01-07T00:00:00Z&start=lt2030-02-20T00:00:00Z", "start"),
        ("start=lt2030-01-08T00:00:00Z", "start"),
    ],
)
def returns_400_naming_start_when_range_is_missing_open_or_over_31_days(
    query: str, named: str
) -> None:
    clinic = make_clinic()

    response = get(f"/fhir/Slot?service-type={clinic.appointment_type.pk}&{query}")

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == [named]


def returns_a_slot_without_patient_or_appointment_and_reads_it_back_by_id() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    first = _search(clinic)[0]

    response = get(f"/fhir/Slot/{first['id']}")

    assert response.status_code == 200
    assert response.json() == first
    assert response.json()["start"] == "2030-01-07T10:00:00Z"
    assert set(first) <= {
        "resourceType",
        "id",
        "meta",
        "status",
        "schedule",
        "serviceType",
        "start",
        "end",
        "extension",
    }


def returns_same_id_when_searched_twice() -> None:
    clinic = make_clinic(rule_fields=HOURS)

    assert [slot["id"] for slot in _search(clinic)] == [slot["id"] for slot in _search(clinic)]


@pytest.mark.parametrize("identifier", ["nonsense", "a.b.c", "x" * 70, "a.b.9999999999999"])
def returns_404_when_slot_id_does_not_parse_or_names_no_offered_slot(identifier: str) -> None:
    response = get(f"/fhir/Slot/{identifier}")

    assert response.status_code == 404
    assert response.json()["resourceType"] == "OperationOutcome"


def returns_404_when_slot_id_names_a_start_off_the_grid() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    first_id = _search(clinic)[0]["id"]
    rule_part, type_part, _ = str(first_id).split(".")
    off_grid = int((FIRST + timedelta(minutes=7)).timestamp() // 60)

    response = get(f"/fhir/Slot/{rule_part}.{type_part}.{off_grid}")

    assert response.status_code == 404


def returns_free_slots_only_when_public_or_patient_asks_for_busy() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=FIRST,
        ends_at=FIRST + HALF_HOUR,
    )

    public = _search(clinic, "&status=busy-tentative")
    patient = _search(clinic, "&status=busy-tentative", token_of(role="PATIENT"))

    assert public == [] and patient == []


def returns_busy_statuses_to_staff_without_naming_a_patient() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    type_fields = {"clinician": clinic.clinician, "appointment_type": clinic.appointment_type}
    make("BookingHold", starts_at=FIRST, ends_at=FIRST + HALF_HOUR, **type_fields)
    make(
        "Appointment",
        patient=clinic.patient,
        starts_at=FIRST + HALF_HOUR,
        ends_at=FIRST + 2 * HALF_HOUR,
        **type_fields,
    )
    make(
        "TimeOff",
        clinician=clinic.clinician,
        starts_at=FIRST + 2 * HALF_HOUR,
        ends_at=FIRST + 3 * HALF_HOUR,
    )
    token = token_of(clinic.clinician.user)

    slots = _search(clinic, "&status=busy&status=busy-tentative&status=busy-unavailable", token)

    assert [slot["status"] for slot in slots] == ["busy-tentative", "busy", "busy-unavailable"]
    assert str(clinic.patient.pk) not in str(slots)
    assert clinic.patient.full_name not in str(slots)


def returns_the_schedule_beside_the_slot_when_include_asks_for_it() -> None:
    clinic = make_clinic(rule_fields=HOURS)

    response = get(
        f"/fhir/Slot?service-type={clinic.appointment_type.pk}&{MONDAY}&_include=Slot:schedule"
    )

    kinds = [entry["resource"]["resourceType"] for entry in response.json()["entry"]]
    assert kinds.count("Slot") == 4 and kinds.count("Schedule") == 1


def returns_the_hidden_clinicians_schedule_only_to_staff() -> None:
    clinic = make_clinic()
    update_row(clinic.clinician.user, is_active=False)

    public = get("/fhir/Schedule")
    staff = get("/fhir/Schedule", token_of(role="ADMIN"))

    assert public.json().get("total", 0) == 0
    assert staff.json()["total"] == 1


def returns_schedule_with_both_actors_and_the_extensions_when_read_by_anyone() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    schedule_id = _search(clinic)[0]["schedule"]["reference"]  # type: ignore[index]

    response = get(f"/fhir/{schedule_id}")

    body = response.json()
    assert body["resourceType"] == "Schedule"
    assert body["planningHorizon"] == {"start": "2030-01-01"}
    assert body["actor"][0]["reference"] == f"Practitioner/{clinic.clinician.user_id}"
    assert response["ETag"].startswith('W/"')


def returns_no_slot_inside_lead_time_for_an_anonymous_caller() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)

    starts = [slot["start"] for slot in _search(clinic)]

    assert starts == ["2030-01-07T08:00:00Z", "2030-01-07T08:30:00Z"]


def returns_no_slot_inside_lead_time_for_a_patient_token() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)

    starts = [slot["start"] for slot in _search(clinic, token=token_of(role="PATIENT"))]

    assert starts == ["2030-01-07T08:00:00Z", "2030-01-07T08:30:00Z"]


def returns_404_when_anonymous_caller_reads_a_slot_inside_lead_time() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)
    staff_view = _search(clinic, token=token_of(role="ADMIN"))
    lead_slots = [slot for slot in staff_view if slot["start"] == "2030-01-07T07:00:00Z"]
    assert len(lead_slots) == 1

    response = get(f"/fhir/Slot/{lead_slots[0]['id']}")

    assert response.status_code == 404
