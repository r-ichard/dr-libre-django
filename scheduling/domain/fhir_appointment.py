"""Task 23a, spec 15.3: one `Appointment` resource type for three origins (ADR 0003): a booked
appointment, a waitlist entry and a booking hold. The clinical note is added only when the
caller says the viewer is that appointment's clinician."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from scheduling.domain.fhir_common import CANONICAL_BASE, Resource, extension, meta, reference
from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus

SERVICE_TYPE_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/service-type"
INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ACCEPTED = "accepted"
SOURCE_EXTENSION = "appointment-source"
STATUS_EXTENSION = "appointment-status"

FHIR_STATUS_OF_APPOINTMENT = {
    AppointmentStatus.BOOKED: "booked",
    AppointmentStatus.CONFIRMED: "booked",
    AppointmentStatus.CHECKED_IN: "checked-in",
    AppointmentStatus.COMPLETED: "fulfilled",
    AppointmentStatus.CANCELLED: "cancelled",
    AppointmentStatus.NO_SHOW: "noshow",
}
INTERNAL_STATUS_OF_FHIR = {
    "checked-in": AppointmentStatus.CHECKED_IN,
    "fulfilled": AppointmentStatus.COMPLETED,
    "noshow": AppointmentStatus.NO_SHOW,
    "cancelled": AppointmentStatus.CANCELLED,
}
FHIR_STATUS_OF_WAITLIST = {
    WaitlistStatus.WAITING: "waitlist",
    WaitlistStatus.OFFERED: "proposed",
    WaitlistStatus.EXPIRED: "cancelled",
}
PENDING = "pending"


@dataclass(frozen=True)
class ServiceFacts:
    type_id: UUID
    type_name: str


@dataclass(frozen=True)
class BookingFacts:
    id: UUID
    version: int
    updated_at: datetime
    status: str
    source: str
    starts_at: datetime
    ends_at: datetime
    service: ServiceFacts
    patient_id: UUID
    practitioner_id: UUID
    room_id: UUID | None
    reason: str
    cancellation_reason: str
    comment: str | None


@dataclass(frozen=True)
class WaitlistFacts:
    id: UUID
    version: int
    updated_at: datetime
    status: str
    service: ServiceFacts
    patient_id: UUID
    earliest_at: datetime
    latest_at: datetime
    preferred_practitioner_id: UUID | None
    offered_starts_at: datetime | None
    offered_ends_at: datetime | None
    offered_practitioner_id: UUID | None


@dataclass(frozen=True)
class HoldFacts:
    id: UUID
    version: int
    updated_at: datetime
    source: str
    starts_at: datetime
    ends_at: datetime
    service: ServiceFacts
    practitioner_id: UUID


def booking_resource(facts: BookingFacts) -> Resource:
    resource = _base(facts.id, facts.version, facts.updated_at, facts.service)
    resource["status"] = FHIR_STATUS_OF_APPOINTMENT[AppointmentStatus(facts.status)]
    resource["start"] = _instant(facts.starts_at)
    resource["end"] = _instant(facts.ends_at)
    participants = [_participant("Patient", facts.patient_id)]
    participants.append(_participant("Practitioner", facts.practitioner_id))
    if facts.room_id is not None:
        participants.append(_participant("Location", facts.room_id))
    resource["participant"] = participants
    extensions = [extension(SOURCE_EXTENSION, "valueCode", facts.source.lower())]
    if resource["status"] == "booked":
        extensions.append(extension(STATUS_EXTENSION, "valueCode", facts.status.lower()))
    resource["extension"] = extensions
    if facts.reason:
        resource["reasonCode"] = [{"text": facts.reason}]
    if facts.cancellation_reason:
        resource["cancelationReason"] = {"text": facts.cancellation_reason}
    if facts.comment:
        resource["comment"] = facts.comment
    return resource


def waitlist_resource(facts: WaitlistFacts) -> Resource:
    resource = _base(facts.id, facts.version, facts.updated_at, facts.service)
    resource["status"] = FHIR_STATUS_OF_WAITLIST[WaitlistStatus(facts.status)]
    participants = [_participant("Patient", facts.patient_id)]
    practitioner_id = facts.offered_practitioner_id or facts.preferred_practitioner_id
    if practitioner_id is not None:
        participants.append(_participant("Practitioner", practitioner_id))
    resource["participant"] = participants
    resource["requestedPeriod"] = [
        {"start": _instant(facts.earliest_at), "end": _instant(facts.latest_at)}
    ]
    if facts.offered_starts_at is not None and facts.offered_ends_at is not None:
        resource["start"] = _instant(facts.offered_starts_at)
        resource["end"] = _instant(facts.offered_ends_at)
    return resource


def hold_resource(facts: HoldFacts) -> Resource:
    resource = _base(facts.id, facts.version, facts.updated_at, facts.service)
    resource["status"] = PENDING
    resource["start"] = _instant(facts.starts_at)
    resource["end"] = _instant(facts.ends_at)
    resource["participant"] = [_participant("Practitioner", facts.practitioner_id)]
    resource["extension"] = [extension(SOURCE_EXTENSION, "valueCode", facts.source.lower())]
    return resource


def _base(identifier: UUID, version: int, updated_at: datetime, service: ServiceFacts) -> Resource:
    coding = {
        "system": SERVICE_TYPE_SYSTEM,
        "code": str(service.type_id),
        "display": service.type_name,
    }
    return {
        "resourceType": "Appointment",
        "id": str(identifier),
        "meta": meta(version, updated_at),
        "serviceType": [{"coding": [coding]}],
    }


def _participant(resource_type: str, identifier: UUID) -> Resource:
    return {"actor": reference(resource_type, identifier), "status": ACCEPTED}


def _instant(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(INSTANT_FORMAT)
