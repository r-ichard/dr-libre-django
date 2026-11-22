"""Task 22, spec 15.2, 15.5: every public resource through the door, search, include, limits."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.models.builders import make
from scheduling.views.pages.search_pages_support import plant_clinic, update_row

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

CLIENT = Client(raise_request_exception=False)


def _get(path: str) -> "_MonkeyPatchedWSGIResponse":
    return CLIENT.get(path)


def _ids(path: str) -> list[str]:
    return [entry["resource"]["id"] for entry in _get(path).json().get("entry", [])]


def returns_healthcare_service_with_duration_when_appointment_type_read() -> None:
    _, appointment_type = plant_clinic()

    body = _get(f"/fhir/HealthcareService/{appointment_type.pk}").json()

    assert body["resourceType"] == "HealthcareService"
    assert body["name"] == "Check-up"
    assert body["providedBy"]["reference"] == f"Organization/{appointment_type.department_id}"
    assert any(item["url"].endswith("service-duration-minutes") for item in body["extension"])


def returns_404_when_appointment_type_is_not_bookable_online() -> None:
    _, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)

    assert _get(f"/fhir/HealthcareService/{appointment_type.pk}").status_code == 404
    assert _ids("/fhir/HealthcareService") == []


def returns_practitioner_role_with_available_time_when_profile_read() -> None:
    clinician, _ = plant_clinic()

    body = _get(f"/fhir/PractitionerRole/{clinician.pk}").json()

    assert body["practitioner"]["reference"] == f"Practitioner/{clinician.user_id}"
    assert body["organization"]["reference"] == f"Organization/{clinician.department_id}"
    assert body["availableTime"][0]["availableStartTime"] == "11:00:00"
    assert body["availableTime"][0]["availableEndTime"] == "14:00:00"


def returns_included_practitioner_after_match_when_include_asked() -> None:
    clinician, _ = plant_clinic()

    body = _get("/fhir/PractitionerRole?_include=PractitionerRole:practitioner").json()

    assert [
        (item["resource"]["resourceType"], item["search"]["mode"]) for item in body["entry"]
    ] == [
        ("PractitionerRole", "match"),
        ("Practitioner", "include"),
    ]
    assert body["entry"][1]["resource"]["id"] == str(clinician.user_id)


def returns_included_department_when_organization_include_asked() -> None:
    clinician, _ = plant_clinic()

    body = _get("/fhir/PractitionerRole?_include=PractitionerRole:organization").json()

    assert body["entry"][1]["resource"]["id"] == str(clinician.department_id)


def returns_code_system_and_value_set_of_specialties_when_read() -> None:
    make("Specialty", code="cardio", name="Cardiology")

    code_system = _get("/fhir/CodeSystem/specialty").json()
    value_set = _get("/fhir/ValueSet/specialty").json()

    assert {"code": "cardio", "display": "Cardiology"} in code_system["concept"]
    assert value_set["compose"]["include"][0]["system"] == code_system["url"]
    assert _get("/fhir/CodeSystem/other").status_code == 404
    assert _get("/fhir/CodeSystem").json()["total"] == 1


def returns_room_location_part_of_hospital_when_room_read() -> None:
    clinician, _ = plant_clinic()
    room = make("Room", department=clinician.department, name="Room 12")

    body = _get(f"/fhir/Location/{room.pk}").json()

    assert body["physicalType"]["coding"][0]["code"] == "ro"
    assert body["partOf"]["reference"] == f"Location/{clinician.department.hospital_id}"
    update_row(room, is_active=False)
    assert _get(f"/fhir/Location/{room.pk}").status_code == 404


def returns_only_hospital_within_distance_when_near_searched() -> None:
    near = make("Hospital", name="Near", latitude=52.52, longitude=13.405)
    make("Hospital", name="Far", latitude=48.14, longitude=11.58)
    make("Hospital", name="Unplaced")

    assert _ids("/fhir/Location?near=52.5|13.4|10|km") == [str(near.pk)]


def returns_names_in_descending_order_when_sort_has_minus() -> None:
    for name in ("Alpha", "Bravo", "Charlie"):
        make("Hospital", name=name)

    ascending = _ids("/fhir/Organization?type=prov&_sort=name")
    descending = _ids("/fhir/Organization?type=prov&_sort=-name")

    assert descending == ascending[::-1]
    assert len(ascending) == 3


def returns_only_departments_when_type_is_dept() -> None:
    clinician, _ = plant_clinic()

    assert _ids("/fhir/Organization?type=dept") == [str(clinician.department_id)]
    assert _ids(f"/fhir/Organization?partof=Organization/{clinician.department.hospital_id}") == [
        str(clinician.department_id)
    ]


def returns_zero_entries_but_total_when_count_is_zero() -> None:
    plant_clinic()

    body = _get("/fhir/Organization?_count=0").json()

    assert body["total"] == 2
    assert body["entry"] == []


def returns_bounded_queries_whatever_the_number_of_rows() -> None:
    for index in range(12):
        _plant_hospital(index)
    paths = [f"/fhir/{item.type}" for item in FHIR_RESOURCES]
    counts: list[int] = []
    for path in paths:
        with CaptureQueriesContext(connection) as captured:
            assert _get(path + "?_count=100").status_code == 200
        counts.append(len(captured))

    assert max(counts) <= 12


def _plant_hospital(index: int) -> None:
    hospital = make("Hospital", name=f"Hospital {index}")
    department = make("Department", hospital=hospital, name=f"Department {index}")
    make("Room", department=department, name=f"Room {index}")
    make("AppointmentType", department=department, name=f"Type {index}")


def returns_every_declared_route_and_declares_every_answering_one() -> None:
    declared = {item.type for item in FHIR_RESOURCES}
    statement = _get("/fhir/metadata").json()["rest"][0]["resource"]

    assert {item["type"] for item in statement} == declared
    for item in statement:
        assert _get(f"/fhir/{item['type']}").status_code == 200
        for parameter in item["searchParam"]:
            assert parameter["name"]
    assert _get("/fhir/Patient").status_code == 404
    assert _get("/fhir/Schedule").status_code == 404


def returns_500_outcome_with_correlation_id_and_no_internals_when_use_case_breaks() -> None:
    with patch("scheduling.views.fhir.views.search_resource", side_effect=RuntimeError("secret")):
        response = CLIENT.get("/fhir/Organization", headers={"X-Correlation-Id": "cid-500"})

    assert response.status_code == 500
    text = response.content.decode()
    assert "secret" not in text
    assert "RuntimeError" not in text
    assert "cid-500" in text
    assert response.json()["resourceType"] == "OperationOutcome"
    assert response["X-Correlation-Id"] == "cid-500"


def returns_400_outcome_when_query_has_too_many_fields() -> None:
    query = "&".join(f"p{index}=1" for index in range(500))

    response = _get(f"/fhir/Organization?{query}")

    assert response.status_code == 400
    assert response.json()["resourceType"] == "OperationOutcome"


def returns_outcome_when_body_is_declared_too_large() -> None:
    response = CLIENT.post("/fhir/Organization", data="x" * 2_000_000, content_type="text/plain")

    assert response.status_code in (400, 413)
    assert response.json()["resourceType"] == "OperationOutcome"


@pytest.mark.parametrize(
    "accept",
    ["application/fhir+json", "application/json", "*/*", "application/*;q=0.5", "text/html, */*"],
)
def returns_200_when_accept_allows_fhir_json(accept: str) -> None:
    assert CLIENT.get("/fhir/CodeSystem", headers={"Accept": accept}).status_code == 200


def returns_inactive_flag_filter_empty_when_only_active_records_are_public() -> None:
    plant_clinic()

    assert _ids("/fhir/Organization?active=false") == []
    assert len(_ids("/fhir/Organization?active=true")) == 2
