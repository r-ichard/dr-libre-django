"""Task 24b: samples of the organisation writes: the body of each create and update for a
department, site, room and appointment type, the answer to a delete, and the refusal of deleting
a hospital that still has departments."""

import json

from django.test import Client

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_outcome import information_outcome
from scheduling.views.fhir.samples_staff import FHIR_JSON, SAMPLE_HOST, fetch_document

SERVER_ASSIGNED = ("id", "meta")
ROLE_SERVER_BUILT = (
    *SERVER_ASSIGNED,
    "active",
    "healthcareService",
    "availableTime",
    "notAvailable",
)
NOT_AVAILABLE_SAMPLE = {
    "description": "Congress",
    "during": {"start": "2030-03-04T08:00:00Z", "end": "2030-03-05T17:00:00Z"},
}


def record_documents(client: Client) -> dict[str, Resource]:
    documents: dict[str, Resource] = {}
    department = _first(client, "Organization", "type=dept")
    site = _first(client, "Location", "type=si")
    room = _first(client, "Location", "type=ro")
    service = _first(client, "HealthcareService")
    for name, resource in (
        ("Organization", department),
        ("Location", site),
        ("Location-room", room),
        ("HealthcareService", service),
    ):
        documents[f"{name}-update-staff"] = resource
        documents[f"{name}-create-staff"] = {
            key: value for key, value in resource.items() if key not in SERVER_ASSIGNED
        }
    for name in ("Organization", "Location", "HealthcareService"):
        documents[f"{name}-delete-staff"] = information_outcome("The record was deleted.", "sample")
    refused = client.delete(
        f"/fhir/Location/{site['id']}", content_type=FHIR_JSON, SERVER_NAME=SAMPLE_HOST
    )
    documents["Location-refusal-staff"] = refused.json()
    return documents


def role_documents(client: Client) -> dict[str, Resource]:
    """The writes of a PractitionerRole: the body of a create, an update and a time off added by
    an update, the answer to a delete, and the refusal of a period changed in place."""
    role = _first(client, "PractitionerRole")
    created = {key: value for key, value in role.items() if key not in ROLE_SERVER_BUILT}
    recorded = {**role, "notAvailable": [NOT_AVAILABLE_SAMPLE]}
    return {
        "PractitionerRole-create-staff": created,
        "PractitionerRole-update-staff": role,
        "PractitionerRole-time-off-staff": recorded,
        "PractitionerRole-delete-staff": information_outcome("The record was deleted.", "sample"),
        "PractitionerRole-refusal-staff": _refusal(client, role),
    }


def practitioner_documents(client: Client) -> dict[str, Resource]:
    """The body of a Practitioner update (an admin's read of it, contact included), the answer to
    a delete, and the refusal of deleting a user that still has a profile."""
    practitioner = _first(client, "Practitioner")
    refused = client.delete(
        f"/fhir/Practitioner/{practitioner['id']}",
        content_type=FHIR_JSON,
        SERVER_NAME=SAMPLE_HOST,
    )
    return {
        "Practitioner-update-staff": practitioner,
        "Practitioner-delete-staff": information_outcome("The record was deleted.", "sample"),
        "Practitioner-refusal-staff": refused.json(),
    }


def _refusal(client: Client, role: Resource) -> Resource:
    """An admin may not record time off: 15.4 gives it to the clinician."""
    attempt = {**role, "notAvailable": [NOT_AVAILABLE_SAMPLE]}
    refused = client.put(
        f"/fhir/PractitionerRole/{role['id']}",
        data=json.dumps(attempt),
        content_type=FHIR_JSON,
        SERVER_NAME=SAMPLE_HOST,
    )
    return refused.json()  # type: ignore[no-any-return]


def _first(client: Client, resource_type: str, search: str = "") -> Resource:
    bundle = fetch_document(client, f"/fhir/{resource_type}?{search}&_count=1")
    return bundle["entry"][0]["resource"]  # type: ignore[index, no-any-return]
