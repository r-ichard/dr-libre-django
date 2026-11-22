"""Task 23a, spec 15.6: an `Appointment` write body read as one command for the use cases the
screens call. The first element the server will not take is named by its FHIR path; the end is
never taken from the client (5.2)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_appointment import INTERNAL_STATUS_OF_FHIR
from scheduling.domain.fhir_body import Shape
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_search import parse_id
from scheduling.domain.fhir_slot_id import parse_slot_id
from scheduling.domain.vocabulary import AppointmentStatus

APPOINTMENT_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "status": str,
    "start": str,
    "end": str,
    "serviceType": [{"coding": [{"system": str, "code": str, "display": str}]}],
    "slot": [{"reference": str}],
    "participant": [{"actor": {"reference": str}, "status": str}],
    "reasonCode": [{"text": str}],
    "cancelationReason": {"text": str},
    "comment": str,
    "requestedPeriod": [{"start": str, "end": str}],
    "extension": [{"url": str, "valueCode": str}],
}
IGNORED_WHEN_COMPARED = ("meta", "status", "start", "end", "cancelationReason")
FHIR_STATUSES = (
    "proposed",
    "pending",
    "booked",
    "arrived",
    "fulfilled",
    "cancelled",
    "noshow",
    "entered-in-error",
    "checked-in",
    "waitlist",
)


@dataclass(frozen=True)
class Book:
    type_id: UUID
    starts_at: datetime
    rule_id: UUID | None
    practitioner_id: UUID | None
    patient_id: UUID | None
    room_id: UUID | None
    reason: str


@dataclass(frozen=True)
class Join:
    type_id: UUID
    earliest_at: datetime
    latest_at: datetime
    practitioner_id: UUID | None
    patient_id: UUID | None


@dataclass(frozen=True)
class Reschedule:
    starts_at: datetime


@dataclass(frozen=True)
class ChangeStatus:
    target: AppointmentStatus
    reason: str


@dataclass(frozen=True)
class InvalidTransition:
    """A valid FHIR status the table of 5.6 does not allow as a target."""


@dataclass(frozen=True)
class NoChange:
    pass


def decode_create(body: dict[str, object]) -> Book | Join | str:
    status = body.get("status")
    if status not in ("proposed", "waitlist"):
        return "Appointment.status"
    type_id = _service_type(body)
    if type_id is None:
        return "Appointment.serviceType"
    actors = _actors(body)
    if isinstance(actors, str):
        return actors
    patient_id, practitioner_id, room_id = actors
    if status == "waitlist":
        return _join(body, type_id, patient_id, practitioner_id)
    return _book(body, type_id, patient_id, practitioner_id, room_id)


def decode_update(
    stored: Resource, body: dict[str, object]
) -> Reschedule | ChangeStatus | InvalidTransition | NoChange | str:
    problem = _moved_element(stored, body)
    if problem is not None:
        return problem
    stored_start, body_start = _read_instant(stored.get("start")), _read_instant(body.get("start"))
    if body_start is None:
        return "Appointment.start"
    status_changed = body.get("status") != stored.get("status")
    if body_start != stored_start:
        return "Appointment.status" if status_changed else Reschedule(body_start)
    if status_changed:
        return _status_change(body)
    if body.get("cancelationReason") != stored.get("cancelationReason"):
        return "Appointment.cancelationReason"
    return NoChange()


def _moved_element(stored: Resource, body: dict[str, object]) -> str | None:
    stored_start, stored_end = _read_instant(stored.get("start")), _read_instant(stored.get("end"))
    body_start, body_end = _read_instant(body.get("start")), _read_instant(body.get("end"))
    if stored_start is None or stored_end is None or body_start is None:
        return "Appointment.start"
    if body_end is None:
        return "Appointment.end"
    if body_end != body_start + (stored_end - stored_start):
        return "Appointment.end"
    names = (set(stored) | set(body)) - set(IGNORED_WHEN_COMPARED)
    return next(
        (f"Appointment.{name}" for name in sorted(names) if stored.get(name) != body.get(name)),
        None,
    )


def _status_change(body: dict[str, object]) -> ChangeStatus | InvalidTransition | str:
    status = body.get("status")
    if status not in FHIR_STATUSES:
        return "Appointment.status"
    target = INTERNAL_STATUS_OF_FHIR.get(str(status))
    if target is None:
        return InvalidTransition()
    reason = _text(body.get("cancelationReason"))
    if target is AppointmentStatus.CANCELLED and not reason:
        return "Appointment.cancelationReason"
    return ChangeStatus(target, reason)


def _book(
    body: dict[str, object],
    type_id: UUID,
    patient_id: UUID | None,
    practitioner_id: UUID | None,
    room_id: UUID | None,
) -> Book | str:
    reason = _first_text(body.get("reasonCode"))
    slots = body.get("slot")
    if isinstance(slots, list) and slots:
        slot = _slot(slots[0], type_id)
        if slot is None:
            return "Appointment.slot"
        return Book(type_id, slot[1], slot[0], practitioner_id, patient_id, room_id, reason)
    starts_at = _read_instant(body.get("start"))
    if starts_at is None:
        return "Appointment.start"
    return Book(type_id, starts_at, None, practitioner_id, patient_id, room_id, reason)


def _join(
    body: dict[str, object], type_id: UUID, patient_id: UUID | None, practitioner_id: UUID | None
) -> Join | str:
    periods = body.get("requestedPeriod")
    period = periods[0] if isinstance(periods, list) and periods else None
    if not isinstance(period, dict):
        return "Appointment.requestedPeriod"
    earliest, latest = _read_instant(period.get("start")), _read_instant(period.get("end"))
    if earliest is None or latest is None:
        return "Appointment.requestedPeriod"
    return Join(type_id, earliest, latest, practitioner_id, patient_id)


def _service_type(body: dict[str, object]) -> UUID | None:
    types = body.get("serviceType")
    if not isinstance(types, list) or len(types) != 1:
        return None
    codings = types[0].get("coding") if isinstance(types[0], dict) else None
    if not isinstance(codings, list) or len(codings) != 1 or not isinstance(codings[0], dict):
        return None
    identifier = parse_id(str(codings[0].get("code", "")))
    return UUID(identifier) if identifier else None


def _actors(body: dict[str, object]) -> tuple[UUID | None, UUID | None, UUID | None] | str:
    found: dict[str, UUID] = {}
    participants = body.get("participant")
    for item in participants if isinstance(participants, list) else []:
        actor = item.get("actor") if isinstance(item, dict) else None
        reference = str(actor.get("reference", "")) if isinstance(actor, dict) else ""
        resource_type, _, text = reference.rpartition("/")
        identifier = parse_id(text)
        if resource_type not in ("Patient", "Practitioner", "Location") or identifier is None:
            return "Appointment.participant"
        if resource_type in found:
            return "Appointment.participant"
        found[resource_type] = UUID(identifier)
    return found.get("Patient"), found.get("Practitioner"), found.get("Location")


def _slot(item: object, type_id: UUID) -> tuple[UUID, datetime] | None:
    reference = str(item.get("reference", "")) if isinstance(item, dict) else ""
    parsed = parse_slot_id(reference.rpartition("/")[2])
    if parsed is None or parsed[1] != type_id or not reference.startswith("Slot/"):
        return None
    return parsed[0], parsed[2]


def _read_instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _text(value: object) -> str:
    return str(value.get("text", "")).strip() if isinstance(value, dict) else ""


def _first_text(value: object) -> str:
    return _text(value[0]) if isinstance(value, list) and value else ""
