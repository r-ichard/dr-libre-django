"""Task 24c, spec 15.2 and 15.4: a PractitionerRole write body read as the fields of a clinician
profile and as changes of its time off. Pure: the console's field checks stay in the use cases."""

from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_clean import without_empty
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_practitioner_role import DEFAULT_TIME_OFF_DESCRIPTION
from scheduling.domain.fhir_record_write import (
    Values,
    extension_value,
    first_coding_code,
    reference_id,
)

NOT_AVAILABLE = "PractitionerRole.notAvailable"
_REFERENCE: Shape = {"reference": str}
ROLE_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "extension": [{"url": str, "valueString": str, "valueInteger": int}],
    "active": bool,
    "practitioner": _REFERENCE,
    "organization": _REFERENCE,
    "specialty": [{"coding": [{"system": str, "code": str, "display": str}]}],
    "healthcareService": [_REFERENCE],
    "location": [_REFERENCE],
    "availableTime": [{"daysOfWeek": [str], "availableStartTime": str, "availableEndTime": str}],
    "notAvailable": [{"id": str, "description": str, "during": {"start": str, "end": str}}],
}
# Elements a body may change; every other one is built by the server and may only be repeated.
CREATE_FREE = frozenset({"extension", "practitioner", "organization", "specialty", "location"})
ADMIN_FREE = frozenset({"extension", "organization", "specialty", "location", "notAvailable"})
OWN_FREE = frozenset({"notAvailable"})
_COMPARED = (
    "extension",
    "active",
    "practitioner",
    "organization",
    "specialty",
    "healthcareService",
    "location",
    "availableTime",
    "notAvailable",
)


@dataclass(frozen=True)
class TimeOffAddition:
    starts_at: datetime
    ends_at: datetime
    reason: str


@dataclass(frozen=True)
class TimeOffChanges:
    additions: tuple[TimeOffAddition, ...]
    removed_ids: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.additions and not self.removed_ids


def role_values(body: Resource) -> Values | str:
    """The profile fields of a body, with the specialty as its code, or the first bad element."""
    user_id = reference_id(body.get("practitioner"), "Practitioner")
    if user_id is None:
        return "PractitionerRole.practitioner"
    department_id = reference_id(body.get("organization"), "Organization")
    if department_id is None:
        return "PractitionerRole.organization"
    specialty_code = first_coding_code(body.get("specialty"))
    if not specialty_code:
        return "PractitionerRole.specialty"
    locations = body.get("location")
    room_id = None
    if isinstance(locations, list) and locations:
        room_id = reference_id(locations[0], "Location")
        if room_id is None:
            return "PractitionerRole.location"
    bio = extension_value(body, "role-bio", "valueString")
    values: Values = {
        "user_id": user_id,
        "department_id": department_id,
        "specialty_code": specialty_code,
        "default_room_id": room_id,
        "bio": bio if isinstance(bio, str) else "",
    }
    weight = extension_value(body, "role-round-robin-weight", "valueInteger")
    if extension_value(body, "role-round-robin-weight", "valueString") is not None:
        return "PractitionerRole.extension"
    if weight is not None:
        values["round_robin_weight"] = weight
    return values


def role_difference(body: Resource, stored: Resource, free: frozenset[str]) -> str:
    """The first element outside `free` that the body does not repeat as stored, or ''."""
    given, kept = _without_empty(body), _without_empty(stored)
    for name in _COMPARED:
        if name not in free and given.get(name) != kept.get(name):
            return f"PractitionerRole.{name}"
    return ""


def _without_empty(resource: Resource) -> Resource:
    """A client never sees an empty array, so it cannot send one back as stored."""
    cleaned = without_empty(resource)
    return cleaned if isinstance(cleaned, dict) else {}


def time_off_changes(body: Resource, stored: Resource) -> TimeOffChanges | str:
    """Entries without an id are recorded, stored ones the body leaves out are removed, a stored
    one that differs is refused: time off is recorded and removed, not edited."""
    stored_by_id = {str(item["id"]): item for item in _entries(stored)}
    kept: set[str] = set()
    additions: list[TimeOffAddition] = []
    for position, entry in enumerate(_entries(body)):
        name = f"{NOT_AVAILABLE}[{position}]"
        entry_id = entry.get("id")
        if entry_id is None:
            added = _addition(entry)
            if added is None:
                return name
            additions.append(added)
            continue
        found = stored_by_id.get(entry_id) if isinstance(entry_id, str) else None
        if found is None or entry_id in kept or not _same_period(entry, found):
            return name
        kept.add(str(entry_id))
    return TimeOffChanges(tuple(additions), tuple(sorted(stored_by_id.keys() - kept)))


def _entries(resource: Resource) -> list[Resource]:
    entries = resource.get("notAvailable")
    return [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []


def _period_of(entry: Resource) -> tuple[datetime, datetime] | None:
    during = entry.get("during")
    if not isinstance(during, dict):
        return None
    try:
        start = datetime.fromisoformat(str(during.get("start")))
        end = datetime.fromisoformat(str(during.get("end")))
    except ValueError:
        return None
    return (start, end) if start.tzinfo is not None and end.tzinfo is not None else None


def _description_of(entry: Resource) -> str:
    description = entry.get("description")
    text = description.strip() if isinstance(description, str) else ""
    return text or DEFAULT_TIME_OFF_DESCRIPTION


def _same_period(entry: Resource, stored: Resource) -> bool:
    period = _period_of(entry)
    return (
        period is not None
        and period == _period_of(stored)
        and _description_of(entry) == _description_of(stored)
    )


def _addition(entry: Resource) -> TimeOffAddition | None:
    period = _period_of(entry)
    if period is None:
        return None
    description = entry.get("description")
    return TimeOffAddition(*period, description if isinstance(description, str) else "")
