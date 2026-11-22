"""Task 24a: samples of Appointment, AppointmentResponse, Communication and AuditEvent: each status
or kind the seed serves, every include, each write body and one refusal. Communication belongs
to its recipient, so its client holds the recipient's token."""

import json
from datetime import timedelta

from django.test import Client
from django.utils import timezone

from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_communication import NOTIFICATION_KIND_WORDS
from scheduling.models import Notification, User
from scheduling.use_cases.api_tokens import issue_token
from scheduling.views.api_clients import fhir_client

SAMPLE_HOST = "localhost"
FHIR_JSON = "application/fhir+json"
APPOINTMENT_INCLUDES = "&".join(
    f"_include=Appointment:{name}" for name in ("patient", "practitioner", "location")
)


def staff_documents(admin_client: Client) -> dict[str, Resource]:
    documents = _appointment_documents(admin_client)
    documents.update(_response_documents(admin_client))
    documents.update(_communication_documents())
    documents.update(_audit_documents(admin_client))
    patient = User.objects.filter(role="PATIENT").first()
    if patient is not None:
        documents["AuditEvent-refusal-staff"] = fetch_document(
            _client_of(patient), "/fhir/AuditEvent"
        )
    return documents


def _client_of(user: User) -> Client:
    return fhir_client(issue_token(user, "fhir-samples").token)


def fetch_document(client: Client, path: str) -> Resource:
    body: Resource = client.get(path, SERVER_NAME=SAMPLE_HOST).json()
    return body


def _write(client: Client, method: str, path: str, body: Resource) -> Resource:
    call = {"post": client.post, "put": client.put}[method]
    answer: Resource = call(
        path, data=json.dumps(body), content_type=FHIR_JSON, SERVER_NAME=SAMPLE_HOST
    ).json()
    return answer


def _entries(bundle: Resource) -> list[Resource]:
    found = bundle.get("entry", [])
    if not isinstance(found, list):
        return []
    return [item["resource"] for item in found if isinstance(item, dict)]


def _appointment_documents(client: Client) -> dict[str, Resource]:
    documents: dict[str, Resource] = {}
    appointments = _entries(fetch_document(client, "/fhir/Appointment?_count=100"))
    for appointment in appointments:
        name = f"Appointment-{appointment['status']}-staff"
        documents.setdefault(name, appointment)
    documents["Appointment-include-staff"] = fetch_document(
        client, f"/fhir/Appointment?_count=5&{APPOINTMENT_INCLUDES}"
    )
    booked = next(item for item in appointments if item["status"] == "booked")
    documents["Appointment-update-staff"] = booked
    create_body = {
        key: value
        for key, value in booked.items()
        if key in ("resourceType", "start", "end", "serviceType", "participant")
    }
    create_body["status"] = "proposed"
    documents["Appointment-create-staff"] = create_body
    past = {**create_body, "start": (timezone.now() - timedelta(days=1)).isoformat()}
    documents["Appointment-refusal-staff"] = _write(client, "post", "/fhir/Appointment", past)
    return documents


def _response_documents(client: Client) -> dict[str, Resource]:
    answered = _entries(fetch_document(client, "/fhir/AppointmentResponse"))[0]
    body = {key: value for key, value in answered.items() if key not in ("id", "meta")}
    refused = {**body, "participantStatus": "declined"}
    return {
        "AppointmentResponse-create-staff": body,
        "AppointmentResponse-refusal-staff": _write(
            client, "post", "/fhir/AppointmentResponse", refused
        ),
    }


def _communication_documents() -> dict[str, Resource]:
    documents: dict[str, Resource] = {}
    for kind in NOTIFICATION_KIND_WORDS:
        notification = Notification.objects.filter(kind=kind).select_related("recipient").first()
        if notification is None:
            continue
        client = _client_of(notification.recipient)
        found = fetch_document(client, f"/fhir/Communication?category={kind}&_count=1")
        documents[f"Communication-{kind.lower()}-staff"] = found
        documents.setdefault("Communication-search-staff", found)
        resource = _entries(found)[0]
        documents.setdefault("Communication-read-staff", resource)
        read = {**resource, "received": timezone.now().isoformat()}
        documents.setdefault("Communication-update-staff", read)
        if "Communication-refusal-staff" not in documents:
            changed = {**resource, "status": "entered-in-error"}
            documents["Communication-refusal-staff"] = _write(
                client, "put", f"/fhir/Communication/{resource['id']}", changed
            )
    return documents


def _audit_documents(client: Client) -> dict[str, Resource]:
    documents: dict[str, Resource] = {}
    for event in _entries(fetch_document(client, "/fhir/AuditEvent?_count=100")):
        documents.setdefault(f"AuditEvent-action-{event['action']}-staff", event)
    return documents
