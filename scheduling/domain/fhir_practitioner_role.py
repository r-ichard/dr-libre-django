"""Task 22, spec 15.2: a clinician profile as a PractitionerRole."""

from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from scheduling.domain.fhir_common import (
    SPECIALTY_SYSTEM,
    Resource,
    extension,
    fhir_instant,
    meta,
    reference,
)

DEFAULT_TIME_OFF_DESCRIPTION = "Time off"
DAYS_FROM_SUNDAY = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


@dataclass(frozen=True)
class RuleHours:
    weekday: int
    start_time: time
    end_time: time


@dataclass(frozen=True)
class TimeOffSource:
    id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str


@dataclass(frozen=True)
class RoleSource:
    id: UUID
    practitioner_id: UUID
    department_id: UUID
    specialty_code: str
    specialty_name: str
    default_room_id: UUID | None
    bio: str
    round_robin_weight: int
    version: int
    updated_at: datetime
    is_active: bool
    service_ids: tuple[UUID, ...]
    rules: tuple[RuleHours, ...]
    time_off: tuple[TimeOffSource, ...] = ()


def practitioner_role(source: RoleSource) -> Resource:
    extensions = [extension("role-round-robin-weight", "valueInteger", source.round_robin_weight)]
    if source.bio:
        extensions.append(extension("role-bio", "valueString", source.bio))
    resource: Resource = {
        "resourceType": "PractitionerRole",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "extension": extensions,
        "active": source.is_active,
        "practitioner": reference("Practitioner", source.practitioner_id),
        "organization": reference("Organization", source.department_id),
        "specialty": [
            {
                "coding": [
                    {
                        "system": SPECIALTY_SYSTEM,
                        "code": source.specialty_code,
                        "display": source.specialty_name,
                    }
                ]
            }
        ],
        "healthcareService": [reference("HealthcareService", item) for item in source.service_ids],
        "availableTime": available_time(source.rules),
    }
    if source.default_room_id is not None:
        resource["location"] = [reference("Location", source.default_room_id)]
    if source.time_off:
        resource["notAvailable"] = [_not_available(item) for item in source.time_off]
    return resource


def _not_available(item: TimeOffSource) -> Resource:
    return {
        "id": str(item.id),
        "description": item.reason or DEFAULT_TIME_OFF_DESCRIPTION,
        "during": {"start": fhir_instant(item.starts_at), "end": fhir_instant(item.ends_at)},
    }


def available_time(rules: tuple[RuleHours, ...]) -> list[Resource]:
    """Rules with the same hours share one entry, with every weekday they run."""
    weekdays_by_hours: dict[tuple[time, time], set[int]] = {}
    for rule in rules:
        weekdays_by_hours.setdefault((rule.start_time, rule.end_time), set()).add(rule.weekday)
    return [
        {
            "daysOfWeek": [DAYS_FROM_SUNDAY[day] for day in sorted(days)],
            "availableStartTime": start.strftime("%H:%M:%S"),
            "availableEndTime": end.strftime("%H:%M:%S"),
        }
        for (start, end), days in sorted(weekdays_by_hours.items())
    ]
