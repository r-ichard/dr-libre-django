"""A patient as a `Patient`, spec 15.2, 15.4 and 15.5, and what a write may change.
A patient changes phone and birth date; an admin name, email and active, as the screens do."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import Resource, meta

PATIENT_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "active": bool,
    "name": [{"text": str}],
    "birthDate": str,
    "telecom": [{"system": str, "value": str}],
}
TELECOM_SYSTEMS = ("email", "phone")
COMPARED_ELEMENTS = ("active", "name", "birthDate")
DAY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
PATIENT_MAY_CHANGE = ("birthDate", "telecom")
ADMIN_MAY_CHANGE = ("active", "name", "telecom.email")


@dataclass(frozen=True)
class PatientSource:
    id: object
    full_name: str
    email: str
    phone: str
    date_of_birth: date | None
    is_active: bool
    version: int
    updated_at: datetime


@dataclass(frozen=True)
class PatientValues:
    full_name: str
    email: str
    phone: str
    birth_date: date | None
    is_active: bool


def patient_resource(source: PatientSource) -> Resource:
    telecom: list[Resource] = [{"system": "email", "value": source.email}]
    if source.phone:
        telecom.append({"system": "phone", "value": source.phone})
    resource: Resource = {
        "resourceType": "Patient",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "active": source.is_active,
        "name": [{"text": source.full_name}],
        "telecom": telecom,
    }
    if source.date_of_birth is not None:
        resource["birthDate"] = source.date_of_birth.isoformat()
    return resource


def refused_changes(
    stored: Resource, body: dict[str, object], allowed: Sequence[str]
) -> tuple[str, ...]:
    """Every element that differs from the stored record and may not change, by name. `meta` is
    the server's and never compared. `telecom` allows the phone; `telecom.email` the email."""
    refused = [
        f"Patient.{element}"
        for element in COMPARED_ELEMENTS
        if element not in allowed and body.get(element) != stored.get(element)
    ]
    stored_telecom, body_telecom = telecom_by_system(stored), telecom_by_system(body)
    for system in TELECOM_SYSTEMS:
        permission = "telecom" if system == "phone" else "telecom.email"
        if permission not in allowed and stored_telecom.get(system) != body_telecom.get(system):
            refused.append(f"Patient.telecom.{system}")
    return tuple(refused)


def patient_values(body: dict[str, object]) -> PatientValues | str:
    """The values a body holds, or the dotted name of the element that cannot be read."""
    telecom = telecom_by_system(body)
    items = body.get("telecom", [])
    if len(telecom) != len(items if isinstance(items, list) else []):
        return "Patient.telecom"
    try:
        born = _birth_date(body.get("birthDate"))
    except ValueError:
        return "Patient.birthDate"
    names = body.get("name", [])
    text = names[0].get("text", "") if isinstance(names, list) and names else ""
    return PatientValues(
        str(text),
        telecom.get("email", ""),
        telecom.get("phone", ""),
        born,
        body.get("active", True) is True,
    )


def telecom_by_system(resource: dict[str, object]) -> dict[str, str]:
    items = resource.get("telecom", [])
    found: dict[str, str] = {}
    for item in items if isinstance(items, list) else []:
        system, value = item.get("system"), item.get("value")
        if system in TELECOM_SYSTEMS and isinstance(value, str) and system not in found:
            found[system] = value
    return found


def _birth_date(raw: object) -> date | None:
    """Raises ValueError for anything that is not a calendar day written `YYYY-MM-DD`."""
    if raw is None:
        return None
    if not isinstance(raw, str) or DAY_PATTERN.fullmatch(raw) is None:
        raise ValueError("not a day")
    return date.fromisoformat(raw)
