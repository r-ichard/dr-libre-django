"""An appointment type as a HealthcareService, spec 15.2."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_common import (
    SPECIALTY_SYSTEM,
    Resource,
    code_identifier,
    extension,
    meta,
    reference,
)


@dataclass(frozen=True)
class ServiceSource:
    id: UUID
    name: str
    version: int
    updated_at: datetime
    is_active: bool
    department_id: UUID
    duration_minutes: int
    buffer_minutes: int
    colour: str
    needs_room: bool
    is_bookable_online: bool
    specialties: tuple[tuple[str, str], ...]
    code: str = ""


def healthcare_service(source: ServiceSource) -> Resource:
    return {
        "resourceType": "HealthcareService",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "extension": [
            extension("service-duration-minutes", "valueInteger", source.duration_minutes),
            extension("service-buffer-minutes", "valueInteger", source.buffer_minutes),
            extension("service-colour", "valueString", source.colour),
            extension("service-needs-room", "valueBoolean", source.needs_room),
            extension("service-bookable-online", "valueBoolean", source.is_bookable_online),
        ],
        "active": source.is_active,
        "providedBy": reference("Organization", source.department_id),
        "type": [{"text": source.name}],
        "specialty": [
            {"coding": [{"system": SPECIALTY_SYSTEM, "code": code, "display": display}]}
            for code, display in source.specialties
        ],
        "name": source.name,
        **code_identifier(source.code),
    }
