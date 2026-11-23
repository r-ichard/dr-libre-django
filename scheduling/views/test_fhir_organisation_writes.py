"""Section 15.4: admins write Organization, Location and HealthcareService, as clients send
them (bearer token, no cookie, no Origin). Expected values come from the plan and spec 15.4."""

from typing import TYPE_CHECKING

import pytest

from scheduling.domain.fhir_common import ORGANIZATION_TYPE_SYSTEM
from scheduling.models import AppointmentType, AuditLogEntry, Department, Hospital, Room
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.fhir_organisation_support import (
    department_body,
    room_body,
    service_body,
    site_body,
)
from scheduling.views.fhir_test_support import NOW, extension, get, send, token_of

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _hospital(**overrides: object) -> Hospital:
    row = make("Hospital", **overrides)
    assert isinstance(row, Hospital)
    return row


def _department(**overrides: object) -> Department:
    row = make("Department", **overrides)
    assert isinstance(row, Department)
    return row


def _post(path: str, body: object, role: str = "ADMIN") -> "_MonkeyPatchedWSGIResponse":
    return send("post", path, body, token_of(role=role))


def _audit_actions() -> list[str]:
    written = AuditLogEntry.objects.exclude(action="api_client.issue")
    return [entry.action for entry in written.order_by("created_at")]


def returns_201_with_location_and_etag_when_admin_posts_a_hospital_site() -> None:
    response = _post("/fhir/Location", site_body())

    hospital = Hospital.objects.get(code="saint-anne")
    assert response.status_code == 201
    assert response["Location"].endswith(f"/fhir/Location/{hospital.pk}")
    assert response["ETag"] == 'W/"1"'
    assert (hospital.city, hospital.time_zone, hospital.phone) == (
        "Hamburg",
        "Europe/Berlin",
        "+49 40 5550",
    )
    assert _audit_actions() == ["hospital.create"]


@pytest.mark.parametrize(
    ("missing", "expression"),
    [
        ("address", "Location.address"),
        ("telecom", "Location.telecom"),
        ("extension", "Location.extension"),
    ],
)
def returns_400_naming_the_element_when_a_hospital_site_lacks_a_place_field(
    missing: str, expression: str
) -> None:
    body = site_body()
    del body[missing]

    response = _post("/fhir/Location", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"][0].startswith(expression)
    assert Hospital.objects.count() == 0


def returns_201_with_location_and_etag_when_admin_posts_a_department() -> None:
    hospital = _hospital()

    response = _post("/fhir/Organization", department_body(hospital))

    department = Department.objects.get(code="cardio")
    assert response.status_code == 201
    assert response["Location"].endswith(f"/fhir/Organization/{department.pk}")
    assert (response["ETag"], department.hospital_id) == ('W/"1"', hospital.pk)
    assert _audit_actions() == ["department.create"]


def returns_201_with_location_and_etag_when_admin_posts_a_room() -> None:
    department = _department()

    response = _post("/fhir/Location", room_body(department))

    room = Room.objects.get(code="room-nine")
    assert response.status_code == 201
    assert (response["ETag"], room.capacity, room.floor) == ('W/"1"', 3, "2")
    assert _audit_actions() == ["room.create"]


def returns_201_with_location_and_etag_when_admin_posts_an_appointment_type() -> None:
    department = _department()

    response = _post("/fhir/HealthcareService", service_body(department))

    appointment_type = AppointmentType.objects.get(code="intake")
    assert response.status_code == 201
    assert (response["ETag"], appointment_type.duration_minutes) == ('W/"1"', 45)
    assert _audit_actions() == ["appointment_type.create"]


def returns_400_when_posting_a_prov_organization() -> None:
    body = department_body(_hospital())
    body["type"] = [{"coding": [{"system": ORGANIZATION_TYPE_SYSTEM, "code": "prov"}]}]

    response = _post("/fhir/Organization", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Organization.type"]


@pytest.mark.parametrize("method", ["put", "delete"])
def returns_405_with_allow_when_writing_a_hospital_organization(method: str) -> None:
    hospital = _hospital()

    response = send(method, f"/fhir/Organization/{hospital.pk}", {}, token_of(role="ADMIN"))

    assert response.status_code == 405
    assert response["Allow"] == "GET"


def returns_200_with_new_etag_when_admin_puts_a_department_with_the_current_if_match() -> None:
    department = _department(name="Before")
    admin = token_of(role="ADMIN")
    body = get(f"/fhir/Organization/{department.pk}", admin).json()
    body["name"] = "After"

    response = send(
        "put", f"/fhir/Organization/{department.pk}", body, admin, **{"If-Match": 'W/"1"'}
    )

    department.refresh_from_db()
    assert response.status_code == 200
    assert (department.name, department.version, response["ETag"]) == ("After", 2, 'W/"2"')
    assert _audit_actions() == ["department.update"]


def returns_200_and_keeps_version_when_a_put_changes_nothing() -> None:
    department = _department()
    admin = token_of(role="ADMIN")
    body = get(f"/fhir/Organization/{department.pk}", admin).json()

    response = send("put", f"/fhir/Organization/{department.pk}", body, admin)

    department.refresh_from_db()
    assert (response.status_code, department.version, _audit_actions()) == (200, 1, [])


def returns_412_when_a_department_put_or_delete_has_a_stale_if_match() -> None:
    department = _department()
    admin = token_of(role="ADMIN")
    body = get(f"/fhir/Organization/{department.pk}", admin).json()
    stale = {"If-Match": 'W/"9"'}

    put = send("put", f"/fhir/Organization/{department.pk}", body, admin, **stale)
    delete = send("delete", f"/fhir/Organization/{department.pk}", {}, admin, **stale)

    assert (put.status_code, delete.status_code) == (412, 412)
    assert Department.objects.filter(pk=department.pk).exists()


def returns_400_naming_identifier_when_the_code_is_taken() -> None:
    hospital = _hospital()
    _department(hospital=hospital, code="cardio")

    response = _post("/fhir/Organization", department_body(hospital, code="CARDIO"))

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Organization.identifier"]


@pytest.mark.parametrize("role", ["CLINICIAN", "PATIENT"])
def returns_403_when_a_clinician_or_patient_token_writes(role: str) -> None:
    department = _department()
    path = f"/fhir/Organization/{department.pk}"
    body = department_body(_hospital())

    answers = [
        _post("/fhir/Organization", body, role).status_code,
        send("put", path, body, token_of(role=role)).status_code,
        send("delete", path, {}, token_of(role=role)).status_code,
    ]

    assert answers == [403, 403, 403]
    assert (Department.objects.count(), _audit_actions()) == (1, [])


def returns_401_when_no_token_writes() -> None:
    department = _department()
    path = f"/fhir/Organization/{department.pk}"
    body = department_body(_hospital())

    answers = [
        send(method, p, body, None).status_code
        for method, p in (("post", "/fhir/Organization"), ("put", path), ("delete", path))
    ]

    assert answers == [401, 401, 401]
    assert Department.objects.count() == 1


def returns_409_has_dependents_naming_counts_when_deleting_a_hospital_site_with_departments() -> (
    None
):
    hospital = _hospital()
    _department(hospital=hospital)
    _department(hospital=hospital)

    response = send("delete", f"/fhir/Location/{hospital.pk}", {}, token_of(role="ADMIN"))

    issue = response.json()["issue"][0]
    assert response.status_code == 409
    assert issue["extension"][0]["valueCode"] == "has_dependents"
    assert "2 departments" in issue["diagnostics"]
    assert Hospital.objects.filter(pk=hospital.pk).exists()


def returns_200_outcome_when_deleting_an_unused_room() -> None:
    room = make("Room")

    response = send("delete", f"/fhir/Location/{room.pk}", {}, token_of(role="ADMIN"))

    assert response.status_code == 200
    assert (Room.objects.filter(pk=room.pk).exists(), _audit_actions()) == (False, ["room.delete"])


def returns_hospital_in_search_then_none_when_a_posted_site_is_deactivated_by_put() -> None:
    admin = token_of(role="ADMIN")
    hospital_id = _post("/fhir/Location", site_body()).json()["id"]
    department = _department(hospital_id=hospital_id)
    make("AppointmentType", department=department)
    clinician = make("ClinicianProfile", department=department)
    make("AvailabilityRule", clinician=clinician)
    shown = browser_api_client().get("/api/v1/search/hospitals").json()["total"]
    body = get(f"/fhir/Location/{hospital_id}", admin).json()
    body["status"] = "inactive"

    send("put", f"/fhir/Location/{hospital_id}", body, admin)

    assert (shown, browser_api_client().get("/api/v1/search/hospitals").json()["total"]) == (1, 0)


def returns_400_naming_city_when_a_site_city_is_over_the_console_limit() -> None:
    body = site_body()
    body["address"] = {
        "line": ["2 Anne Street"],
        "city": "x" * 101,
        "postalCode": "1",
        "country": "DE",
    }

    response = _post("/fhir/Location", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Location.address.city"]
    assert Hospital.objects.count() == 0


def returns_400_naming_the_element_when_a_site_gives_a_derived_element() -> None:
    body = site_body()
    body["managingOrganization"] = {"reference": f"Organization/{_hospital().pk}"}

    response = _post("/fhir/Location", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Location.managingOrganization"]


def returns_inactive_room_when_a_room_is_posted_with_status_inactive() -> None:
    body = room_body(_department())
    body["status"] = "inactive"

    response = _post("/fhir/Location", body)

    assert response.status_code == 201
    assert Room.objects.get(code="room-nine").is_active is False


def returns_400_naming_the_extension_when_a_room_lacks_a_capacity() -> None:
    body = room_body(_department())
    body["extension"] = [extension("room-floor", valueString="2")]

    response = _post("/fhir/Location", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["Location.extension"]
    assert Room.objects.count() == 0


def returns_flags_as_sent_when_an_appointment_type_is_posted() -> None:
    department = _department()
    flipped = service_body(department, code="flip")
    required = [
        extension("service-duration-minutes", valueInteger=30),
        extension("service-buffer-minutes", valueInteger=0),
        extension("service-colour", valueString="#112233"),
    ]
    flipped["extension"] = [
        *required,
        extension("service-needs-room", valueBoolean=True),
        extension("service-bookable-online", valueBoolean=False),
    ]
    bare = service_body(department, code="bare")
    bare["extension"] = required

    _post("/fhir/HealthcareService", flipped)
    _post("/fhir/HealthcareService", bare)

    flags = {
        row.code: (row.needs_room, row.is_bookable_online) for row in AppointmentType.objects.all()
    }
    assert flags == {"flip": (True, False), "bare": (False, False)}


def returns_400_naming_active_when_an_appointment_type_lacks_active() -> None:
    body = service_body(_department())
    del body["active"]

    response = _post("/fhir/HealthcareService", body)

    assert response.status_code == 400
    assert response.json()["issue"][0]["expression"] == ["HealthcareService.active"]
