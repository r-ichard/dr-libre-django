"""Sections 15.1, 15.2 and 15.4: the public FHIR door, read and search, no token."""

from typing import TYPE_CHECKING

import pytest

from scheduling.models.builders import make
from scheduling.views.api_clients import fhir_client
from scheduling.views.pages.search_pages_support import (
    PLANTED_BIRTH,
    PLANTED_EMAIL,
    PLANTED_PHONE,
    plant_clinic,
    update_row,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

FHIR_JSON = "application/fhir+json"


def _get(path: str, accept: str = "", correlation_id: str = "") -> "_MonkeyPatchedWSGIResponse":
    headers = {"Accept": accept} if accept else {}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    return fhir_client().get(path, headers=headers)


def _is_outcome(response: "_MonkeyPatchedWSGIResponse") -> bool:
    return bool(response.json().get("resourceType") == "OperationOutcome")


def returns_organization_of_type_prov_when_hospital_read() -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital

    response = _get(f"/fhir/Organization/{hospital.pk}")

    assert response.status_code == 200
    body = response.json()
    assert (body["resourceType"], body["id"]) == ("Organization", str(hospital.pk))
    assert body["type"][0]["coding"][0]["code"] == "prov"


def returns_department_organization_part_of_hospital_when_department_read() -> None:
    clinician, _ = plant_clinic()
    department = clinician.department

    response = _get(f"/fhir/Organization/{department.pk}")

    body = response.json()
    assert body["type"][0]["coding"][0]["code"] == "dept"
    assert body["partOf"]["reference"] == f"Organization/{department.hospital.pk}"


def returns_site_location_with_city_and_time_zone_when_hospital_read_as_location() -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital

    response = _get(f"/fhir/Location/{hospital.pk}")

    body = response.json()
    assert body["address"]["city"] == "Berlin"
    assert body["physicalType"]["coding"][0]["code"] == "si"


def returns_version_id_and_weak_etag_when_resource_read() -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital

    response = _get(f"/fhir/Organization/{hospital.pk}")

    assert response.json()["meta"]["versionId"] == str(hospital.version)
    assert response["ETag"] == f'W/"{hospital.version}"'


def returns_fhir_json_and_correlation_id_when_any_response_sent() -> None:
    response = _get("/fhir/Organization/not-a-uuid", correlation_id="abc-123")

    assert response["Content-Type"].startswith(FHIR_JSON)
    assert response["X-Correlation-Id"] == "abc-123"


def returns_practitioner_without_email_phone_or_birth_date_when_no_token() -> None:
    clinician, _ = plant_clinic()

    response = _get(f"/fhir/Practitioner/{clinician.user.pk}")

    assert response.status_code == 200
    text = response.content.decode()
    for private in (PLANTED_EMAIL, PLANTED_PHONE, PLANTED_BIRTH):
        assert private not in text


def returns_404_outcome_when_clinician_has_no_online_bookable_type() -> None:
    clinician, appointment_type = plant_clinic()
    update_row(appointment_type, is_bookable_online=False)

    response = _get(f"/fhir/Practitioner/{clinician.user.pk}")

    assert response.status_code == 404
    assert _is_outcome(response)


def returns_404_outcome_when_hospital_inactive_and_no_token() -> None:
    clinician, _ = plant_clinic()
    hospital = clinician.department.hospital
    update_row(hospital, is_active=False)

    response = _get(f"/fhir/Organization/{hospital.pk}")

    assert response.status_code == 404
    assert _is_outcome(response)


def returns_searchset_bundle_with_total_and_self_when_organizations_searched() -> None:
    plant_clinic()

    response = _get("/fhir/Organization?name=Riverside")

    body = response.json()
    assert (body["resourceType"], body["type"], body["total"]) == ("Bundle", "searchset", 1)
    assert [link["relation"] for link in body["link"]] == ["self"]


def returns_every_page_once_when_next_links_followed() -> None:
    for index in range(45):
        make("Hospital", name=f"Paged {index:02d}")
    seen: list[str] = []
    path: str | None = "/fhir/Organization?_count=20&_sort=name"

    while path:
        body = _get(path).json()
        seen += [entry["resource"]["id"] for entry in body["entry"]]
        urls = {link["relation"]: link["url"] for link in body["link"]}
        path = urls["next"].split("testserver", 1)[-1] if "next" in urls else None

    assert len(seen) == 45
    assert len(set(seen)) == 45


@pytest.mark.parametrize(
    "query",
    [
        "/fhir/Organization?colour=red",
        "/fhir/Organization?active=maybe",
        "/fhir/Organization?_count=101",
        "/fhir/Organization?_count=abc",
        "/fhir/Organization?name=a&name=b",
        "/fhir/Organization?access_token=x",
        "/fhir/Practitioner?_include=PractitionerRole:practitioner",
        "/fhir/Location?near=1|2|5000|km",
    ],
)
def returns_400_outcome_naming_the_parameter_when_search_parameter_refused(query: str) -> None:
    response = _get(query)

    assert response.status_code == 400
    assert _is_outcome(response)
    assert response.json()["issue"][0]["expression"] == [
        query.split("?")[1].split("=")[0].split("&")[0]
    ]


@pytest.mark.parametrize("path", ["/fhir/Nothing", "/fhir/Organization/" + "0" * 32, "/fhir/x/y/z"])
def returns_404_outcome_when_type_or_id_unknown(path: str) -> None:
    response = _get(path)

    assert response.status_code == 404
    assert _is_outcome(response)


def returns_405_outcome_when_method_is_not_a_read() -> None:
    response = fhir_client().post("/fhir/Practitioner", data="{}", content_type=FHIR_JSON)

    assert response.status_code == 405
    assert _is_outcome(response)


def returns_406_outcome_when_html_is_asked_for() -> None:
    response = _get("/fhir/Organization", accept="text/html")

    assert response.status_code == 406
    assert _is_outcome(response)


def returns_capability_statement_declaring_all_fourteen_resources() -> None:
    response = _get("/fhir/metadata")

    body = response.json()
    assert body["resourceType"] == "CapabilityStatement"
    assert body["fhirVersion"] == "4.0.1"
    declared = {resource["type"] for resource in body["rest"][0]["resource"]}
    assert declared == {
        "Organization",
        "Location",
        "HealthcareService",
        "CodeSystem",
        "ValueSet",
        "Practitioner",
        "PractitionerRole",
        "Schedule",
        "Slot",
        "Patient",
        "Appointment",
        "AppointmentResponse",
        "Communication",
        "AuditEvent",
    }
