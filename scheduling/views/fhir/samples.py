"""Task 22a: one sample of everything /fhir can answer, as the public and as a staff token,
read through the real routes. `make fhir-validate` hands them to the HL7 validator and a test
walks them for empty values."""

import json
from datetime import timedelta
from pathlib import Path

from django.test import Client
from django.utils import timezone

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.domain.fhir_outcome import information_outcome
from scheduling.models import User
from scheduling.use_cases.api_tokens import issue_token
from scheduling.views.api_clients import fhir_client
from scheduling.views.fhir.samples_records import record_documents
from scheduling.views.fhir.samples_staff import fetch_document, staff_documents

VIEWS = ("public", "staff")
NEEDS_MORE = ("Slot", "Patient")  # a start range and a type; a token
SLOT_DAYS = 14
MISSING_PATH = "/fhir/Organization/00000000-0000-0000-0000-000000000000"


def sample_documents(staff_user: User) -> dict[str, Resource]:
    """File name to JSON body. The staff user's token is created here and kept nowhere."""
    token = issue_token(staff_user, "fhir-samples").token
    documents: dict[str, Resource] = {}
    for view in VIEWS:
        client = fhir_client(token if view == "staff" else None)
        documents.update(_view_documents(client, view))
        documents.update(_slot_documents(client, view))
    documents.update(_staff_documents(fhir_client(token)))
    return documents


def _view_documents(client: Client, view: str) -> dict[str, Resource]:
    documents: dict[str, Resource] = {}
    for declaration in FHIR_RESOURCES:
        name = declaration.type
        if name in NEEDS_MORE:
            continue
        bundle = fetch_document(client, f"/fhir/{name}")
        documents[f"{name}-search-{view}"] = bundle
        identifiers = [entry["resource"]["id"] for entry in bundle.get("entry", [])]  # type: ignore[attr-defined]
        if identifiers:
            documents[f"{name}-read-{view}"] = fetch_document(
                client, f"/fhir/{name}/{identifiers[0]}"
            )
    include = "_include=PractitionerRole:practitioner&_include=PractitionerRole:organization"
    documents[f"PractitionerRole-include-{view}"] = fetch_document(
        client, f"/fhir/PractitionerRole?{include}"
    )
    documents[f"metadata-{view}"] = fetch_document(client, "/fhir/metadata")
    documents[f"OperationOutcome-{view}"] = fetch_document(client, MISSING_PATH)
    return documents


def _slot_documents(client: Client, view: str) -> dict[str, Resource]:
    """Slots of the first service the demo seed offers any, as the public and as staff."""
    today = timezone.now().date()
    window = f"start=ge{today}&start=lt{today + timedelta(days=SLOT_DAYS)}"
    services = fetch_document(client, "/fhir/HealthcareService?_count=100").get("entry", [])
    for entry in services:  # type: ignore[attr-defined]
        base = f"/fhir/Slot?service-type={entry['resource']['id']}&{window}"
        bundle = fetch_document(client, base)
        if bundle.get("entry"):
            documents = {f"Slot-search-{view}": bundle}
            first = bundle["entry"][0]["resource"]  # type: ignore[index]
            documents[f"Slot-read-{view}"] = fetch_document(client, f"/fhir/Slot/{first['id']}")
            documents[f"Slot-include-{view}"] = fetch_document(
                client, f"{base}&_include=Slot:schedule"
            )
            busy = "&status=free&status=busy&status=busy-tentative&status=busy-unavailable"
            documents[f"Slot-busy-{view}"] = fetch_document(client, base + busy)
            return documents
    return {}


def _staff_documents(client: Client) -> dict[str, Resource]:
    """Patient reads, the request bodies of every write, and the answer to a delete."""
    documents: dict[str, Resource] = {}
    patients = fetch_document(client, "/fhir/Patient")
    documents["Patient-search-staff"] = patients
    first_patient = patients["entry"][0]["resource"]  # type: ignore[index]
    documents["Patient-read-staff"] = fetch_document(client, f"/fhir/Patient/{first_patient['id']}")
    documents["Patient-update-staff"] = first_patient
    schedule = fetch_document(client, "/fhir/Schedule")["entry"][0]["resource"]  # type: ignore[index]
    documents["Schedule-update-staff"] = schedule
    documents["Schedule-create-staff"] = {
        key: value for key, value in schedule.items() if key not in ("id", "meta")
    }
    documents["Schedule-delete-staff"] = information_outcome("The record was deleted.", "sample")
    documents.update(staff_documents(client))
    documents.update(record_documents(client))
    return documents


def write_samples(staff_user: User, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in sample_documents(staff_user).items():
        path = directory / f"{name}.json"
        path.write_text(json.dumps(body, indent=2))
        written.append(path)
    return written
