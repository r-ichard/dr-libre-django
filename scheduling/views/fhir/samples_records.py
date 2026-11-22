"""Task 24b: samples of the organisation writes: the body of each create and update for a
department, site, room and appointment type, the answer to a delete, and the refusal of deleting
a hospital that still has departments."""

from django.test import Client

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_outcome import information_outcome
from scheduling.views.fhir.samples_staff import FHIR_JSON, SAMPLE_HOST, fetch_document

SERVER_ASSIGNED = ("id", "meta")


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


def _first(client: Client, resource_type: str, search: str = "") -> Resource:
    bundle = fetch_document(client, f"/fhir/{resource_type}?{search}&_count=1")
    return bundle["entry"][0]["resource"]  # type: ignore[index, no-any-return]
