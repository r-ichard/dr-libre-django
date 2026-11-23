"""An availability rule as a `Schedule`, spec 15.2 and 15.4, and a `Schedule` body back
into the fields of a rule. Weekday, times and step travel as extensions of our own."""

from dataclasses import dataclass
from datetime import date, datetime, time
from uuid import UUID

from scheduling.domain.fhir_body import Shape, exact_elements
from scheduling.domain.fhir_common import Resource, extension, extension_url, meta, reference
from scheduling.domain.fhir_search import parse_id

WEEKDAY = "schedule-weekday"
START_TIME = "schedule-start-time"
END_TIME = "schedule-end-time"
SLOT_STEP = "schedule-slot-step-minutes"
EXTENSION_VALUES = {WEEKDAY: "valueInteger", START_TIME: "valueTime", END_TIME: "valueTime"}
EXTENSION_VALUES[SLOT_STEP] = "valueInteger"
SCHEDULE_SHAPE: Shape = {
    "resourceType": str,
    "id": str,
    "meta": {"versionId": str, "lastUpdated": str},
    "active": bool,
    "actor": [{"reference": str}],
    "planningHorizon": {"start": str, "end": str},
    "extension": [{"url": str, "valueInteger": int, "valueTime": str}],
}


@dataclass(frozen=True)
class ScheduleSource:
    id: UUID
    version: int
    updated_at: datetime
    practitioner_id: UUID
    room_id: UUID | None
    valid_from: date
    valid_to: date | None
    weekday: int
    start_time: time
    end_time: time
    slot_step_minutes: int
    is_active: bool


@dataclass(frozen=True)
class ScheduleFields:
    practitioner_id: UUID
    room_id: UUID | None
    weekday: int
    start_time: time
    end_time: time
    slot_step_minutes: int


def schedule_resource(source: ScheduleSource) -> Resource:
    actors = [reference("Practitioner", source.practitioner_id)]
    if source.room_id is not None:
        actors.append(reference("Location", source.room_id))
    return {
        "resourceType": "Schedule",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "extension": [
            extension(WEEKDAY, "valueInteger", source.weekday),
            extension(START_TIME, "valueTime", source.start_time.strftime("%H:%M:%S")),
            extension(END_TIME, "valueTime", source.end_time.strftime("%H:%M:%S")),
            extension(SLOT_STEP, "valueInteger", source.slot_step_minutes),
        ],
        "active": source.is_active,
        "actor": actors,
        "planningHorizon": horizon(source.valid_from, source.valid_to),
    }


def horizon(valid_from: date, valid_to: date | None) -> Resource:
    period: Resource = {"start": valid_from.isoformat()}
    if valid_to is not None:
        period["end"] = valid_to.isoformat()
    return period


def schedule_fields(body: dict[str, object]) -> ScheduleFields | str:
    """The rule fields a body asks for, or the dotted name of the element that is wrong."""
    wrong = exact_elements(body, SCHEDULE_SHAPE, "Schedule")
    if wrong is not None:
        return wrong
    values = _extension_values(body)
    if isinstance(values, str):
        return values
    actors = _actors(body)
    if isinstance(actors, str):
        return actors
    weekday, step = values[WEEKDAY], values[SLOT_STEP]
    start, end = _time(values[START_TIME]), _time(values[END_TIME])
    if not isinstance(weekday, int) or not isinstance(step, int):
        return "Schedule.extension"
    if start is None:
        return "Schedule.extension.schedule-start-time"
    if end is None:
        return "Schedule.extension.schedule-end-time"
    return ScheduleFields(actors[0], actors[1], weekday, start, end, step)


def server_owned_problem(body: dict[str, object], expected_horizon: Resource) -> str | None:
    """`active` and `planningHorizon` are set by the server; a body may only repeat them."""
    if body.get("active", True) is not True:
        return "Schedule.active"
    if body.get("planningHorizon", expected_horizon) != expected_horizon:
        return "Schedule.planningHorizon"
    return None


def _extension_values(body: dict[str, object]) -> dict[str, object] | str:
    found: dict[str, object] = {}
    items = body.get("extension", [])
    for item in items if isinstance(items, list) else []:
        name = str(item.get("url", "")).removeprefix(extension_url(""))
        key = EXTENSION_VALUES.get(name)
        if key is None or name in found or key not in item:
            return f"Schedule.extension.{name or 'url'}"
        found[name] = item[key]
    missing = next((name for name in EXTENSION_VALUES if name not in found), None)
    return found if missing is None else f"Schedule.extension.{missing}"


def _actors(body: dict[str, object]) -> tuple[UUID, UUID | None] | str:
    practitioners: list[UUID] = []
    rooms: list[UUID] = []
    actors = body.get("actor", [])
    for item in actors if isinstance(actors, list) else []:
        kind, _, text = str(item.get("reference", "")).partition("/")
        identifier = parse_id(text)
        if identifier is None or kind not in ("Practitioner", "Location"):
            return "Schedule.actor"
        (practitioners if kind == "Practitioner" else rooms).append(UUID(identifier))
    if len(practitioners) != 1 or len(rooms) > 1:
        return "Schedule.actor"
    return practitioners[0], (rooms[0] if rooms else None)


def _time(text: object) -> time | None:
    try:
        parsed = time.fromisoformat(str(text))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None and len(str(text)) == len("00:00:00") else None
