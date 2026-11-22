"""Task 22, spec 15.2 and 15.4: a clinician user as a Practitioner. A public caller's source has
no contact, so a public body cannot carry email or phone; birth date is never given."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_common import Resource, meta


@dataclass(frozen=True)
class PractitionerContact:
    email: str
    phone: str


@dataclass(frozen=True)
class PractitionerSource:
    id: UUID
    full_name: str
    title: str
    version: int
    updated_at: datetime
    is_active: bool
    contact: PractitionerContact | None = None


def practitioner(source: PractitionerSource) -> Resource:
    body: Resource = {
        "resourceType": "Practitioner",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "active": source.is_active,
        "name": [{"text": source.full_name}],
        "qualification": [{"code": {"text": source.title}}],
    }
    if source.contact is not None:
        telecom = [{"system": "email", "value": source.contact.email}]
        if source.contact.phone:
            telecom.append({"system": "phone", "value": source.contact.phone})
        body["telecom"] = telecom
    return body
