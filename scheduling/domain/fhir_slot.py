"""A free or busy start of a schedule as a `Slot`, spec 15.2 and 15.6. A slot is computed
and never stored; it names its schedule and service, never a patient or an appointment."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.fhir_common import CANONICAL_BASE, Resource, reference
from scheduling.domain.fhir_slot_id import slot_id
from scheduling.domain.free_slots import AvailabilityWindow

SERVICE_TYPE_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/service-type"
DAYS_PER_WEEK = 7
INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ACTOR_PARAMETER = "schedule.actor"
SEARCH_NAMES = ("start", "service-type", "schedule", ACTOR_PARAMETER, "status")


@dataclass(frozen=True)
class SlotSource:
    rule_id: UUID
    type_id: UUID
    type_name: str
    start: datetime
    duration: timedelta
    status: str


@dataclass(frozen=True)
class RuleCover:
    id: UUID
    window: AvailabilityWindow


def slot_resource(source: SlotSource) -> Resource:
    return {
        "resourceType": "Slot",
        "id": slot_id(source.rule_id, source.type_id, source.start),
        "serviceType": [
            {
                "coding": [
                    {
                        "system": SERVICE_TYPE_SYSTEM,
                        "code": str(source.type_id),
                        "display": source.type_name,
                    }
                ]
            }
        ],
        "schedule": reference("Schedule", source.rule_id),
        "status": source.status,
        "start": _instant(source.start),
        "end": _instant(source.start + source.duration),
    }


def schedule_of(rules: list[RuleCover], start: datetime, zone: ZoneInfo) -> UUID | None:
    """The rule whose weekday, local hours and validity cover a start. A clinician's rules of one
    weekday never overlap, so at most one does."""
    local = start.astimezone(zone)
    weekday = local.isoweekday() % DAYS_PER_WEEK
    for rule in rules:
        window = rule.window
        if (
            window.weekday == weekday
            and window.valid_from <= local.date()
            and (window.valid_to is None or local.date() <= window.valid_to)
            and window.start_time <= local.time() < window.end_time
        ):
            return rule.id
    return None


def _instant(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(INSTANT_FORMAT)
