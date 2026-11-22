"""Task 24, spec 15.2, 15.4, 15.5: a notification as a `Communication`, and what an update of it
may do: set `received` once. Every other change is refused and named."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import (
    CANONICAL_BASE,
    Resource,
    coding,
    fhir_instant,
    meta,
    reference,
)

COMMUNICATION_TYPE = "Communication"
KIND_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/notification-kind"
COMMUNICATION_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "status": str,
    "category": [{"coding": [{"system": str, "code": str, "display": str}]}],
    "recipient": [{"reference": str}],
    "about": [{"reference": str}],
    "payload": [{"contentString": str}],
    "sent": str,
    "received": str,
}
NOTIFICATION_KIND_WORDS = {
    "APPOINTMENT_REMINDER": "Appointment reminder",
    "APPOINTMENT_CANCELLED": "Appointment cancelled",
    "SCHEDULE_CHANGED": "Schedule changed",
    "WAITLIST_OFFERED": "Waitlist offered",
    "WAITLIST_BOOKED": "Waitlist booked",
}
IGNORED_WHEN_COMPARED = ("meta", "received")


@dataclass(frozen=True)
class CommunicationFacts:
    id: UUID
    version: int
    updated_at: datetime
    kind: str
    recipient_type: str
    recipient_id: UUID
    title: str
    body: str
    sent_at: datetime
    read_at: datetime | None
    about_id: UUID | None


@dataclass(frozen=True)
class MarkRead:
    pass


@dataclass(frozen=True)
class NoChange:
    pass


def communication_resource(facts: CommunicationFacts) -> Resource:
    text = f"{facts.title}\n{facts.body}" if facts.body else facts.title
    resource: Resource = {
        "resourceType": COMMUNICATION_TYPE,
        "id": str(facts.id),
        "meta": meta(facts.version, facts.updated_at),
        "status": "completed",
        "category": [coding(KIND_SYSTEM, facts.kind, NOTIFICATION_KIND_WORDS[facts.kind])],
        "recipient": [reference(facts.recipient_type, facts.recipient_id)],
        "payload": [{"contentString": text}],
        "sent": fhir_instant(facts.sent_at),
    }
    if facts.about_id is not None:
        resource["about"] = [reference("Appointment", facts.about_id)]
    if facts.read_at is not None:
        resource["received"] = fhir_instant(facts.read_at)
    return resource


def decode_update(stored: Resource, body: dict[str, object]) -> MarkRead | NoChange | str:
    """What the body asks, as the caller sees the stored resource, or the dotted name refused."""
    names = sorted((set(stored) | set(body)) - set(IGNORED_WHEN_COMPARED))
    for name in names:
        if stored.get(name) != body.get(name):
            return f"{COMMUNICATION_TYPE}.{name}"
    received = body.get("received")
    if received == stored.get("received"):
        return NoChange()
    if "received" in stored or not _is_date_time(received):
        return f"{COMMUNICATION_TYPE}.received"
    return MarkRead()


def _is_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True
