"""Task 22, spec 15.2 and 15.4: a clinician user as a Practitioner. A public caller's source has
no contact, so a public body cannot carry email or phone; birth date is never given."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import Resource, meta
from scheduling.domain.fhir_patient import telecom_by_system

PRACTITIONER_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "active": bool,
    "name": [{"text": str}],
    "telecom": [{"system": str, "value": str}],
    "qualification": [{"code": {"text": str}}],
}
TELECOM_ELEMENT = "Practitioner.telecom"


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


@dataclass(frozen=True)
class PractitionerValues:
    full_name: str
    email: str
    title: str | None
    is_active: bool


def refused_practitioner_changes(stored: Resource, body: dict[str, object]) -> tuple[str, ...]:
    """The console cannot edit a phone, so a phone that differs from the stored one is refused."""
    if telecom_by_system(stored).get("phone") != telecom_by_system(body).get("phone"):
        return (TELECOM_ELEMENT,)
    return ()


def practitioner_values(body: dict[str, object], stored: Resource) -> PractitionerValues | str:
    """The console's values a body holds, or the dotted name of the element that cannot be read.
    An absent `active` or `qualification` leaves the stored value; an absent name is empty."""
    telecom = telecom_by_system(body)
    items = body.get("telecom", [])
    if len(telecom) != len(items if isinstance(items, list) else []):
        return TELECOM_ELEMENT
    names = body.get("name", [])
    text = names[0].get("text", "") if isinstance(names, list) and names else ""
    return PractitionerValues(
        str(text),
        telecom.get("email", ""),
        _title(body),
        body.get("active", stored.get("active", True)) is True,
    )


def _title(body: dict[str, object]) -> str | None:
    qualifications = body.get("qualification", [])
    if not isinstance(qualifications, list) or not qualifications:
        return None
    code = qualifications[0].get("code", {})
    return str(code.get("text", "")) if isinstance(code, dict) else None
