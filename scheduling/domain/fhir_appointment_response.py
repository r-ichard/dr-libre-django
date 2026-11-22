"""Task 24, spec 15.2, 15.4, 15.5: a booked waitlist entry as an `AppointmentResponse` with
participant status `accepted`, and the body that accepts an offer. Declining is not in the
specification, so no other status is ever shown or accepted."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import Resource, fhir_instant, meta, reference

ACCEPTED = "accepted"
RESPONSE_TYPE = "AppointmentResponse"
RESPONSE_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "appointment": {"reference": str},
    "start": str,
    "end": str,
    "participantStatus": str,
    "actor": {"reference": str},
}


@dataclass(frozen=True)
class ResponseFacts:
    entry_id: UUID
    version: int
    updated_at: datetime
    patient_id: UUID
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class Acceptance:
    entry_id: UUID
    patient_id: UUID


def response_resource(facts: ResponseFacts) -> Resource:
    return {
        "resourceType": RESPONSE_TYPE,
        "id": str(facts.entry_id),
        "meta": meta(facts.version, facts.updated_at),
        "appointment": reference("Appointment", facts.entry_id),
        "start": fhir_instant(facts.starts_at),
        "end": fhir_instant(facts.ends_at),
        "participantStatus": ACCEPTED,
        "actor": reference("Patient", facts.patient_id),
    }


def decode_acceptance(body: dict[str, object]) -> Acceptance | str:
    """The entry and patient a body accepts for, or the dotted name of the first element refused."""
    if body.get("participantStatus") != ACCEPTED:
        return f"{RESPONSE_TYPE}.participantStatus"
    entry_id = _referenced("Appointment", body.get("appointment"))
    if entry_id is None:
        return f"{RESPONSE_TYPE}.appointment"
    patient_id = _referenced("Patient", body.get("actor"))
    if patient_id is None:
        return f"{RESPONSE_TYPE}.actor"
    return Acceptance(entry_id, patient_id)


def _referenced(resource_type: str, element: object) -> UUID | None:
    if not isinstance(element, dict):
        return None
    kind, _, identifier = str(element.get("reference", "")).partition("/")
    try:
        return UUID(identifier) if kind == resource_type else None
    except ValueError:
        return None
