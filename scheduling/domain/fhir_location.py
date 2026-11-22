"""Task 22, spec 15.2: a hospital site and a room as a Location."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_common import (
    LOCATION_TYPE_SYSTEM,
    Resource,
    code_identifier,
    coding,
    extension,
    meta,
    reference,
)


@dataclass(frozen=True)
class SiteSource:
    id: UUID
    name: str
    version: int
    updated_at: datetime
    is_active: bool
    street_address: str
    postal_code: str
    city: str
    country: str
    phone: str
    time_zone: str
    latitude: float | None
    longitude: float | None
    code: str = ""


@dataclass(frozen=True)
class RoomSource:
    id: UUID
    name: str
    version: int
    updated_at: datetime
    is_active: bool
    hospital_id: UUID
    department_id: UUID
    floor: str
    capacity: int
    equipment: tuple[str, ...]
    code: str = ""


def site_location(source: SiteSource) -> Resource:
    resource: Resource = {
        "resourceType": "Location",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "extension": [extension("hospital-time-zone", "valueCode", source.time_zone)],
        "status": _status(source.is_active),
        "name": source.name,
        "telecom": [{"system": "phone", "value": source.phone}],
        "address": {
            "line": [source.street_address],
            "city": source.city,
            "postalCode": source.postal_code,
            "country": source.country,
        },
        "physicalType": coding(LOCATION_TYPE_SYSTEM, "si", "Site"),
        "managingOrganization": reference("Organization", source.id),
        **code_identifier(source.code),
    }
    if source.latitude is not None and source.longitude is not None:
        resource["position"] = {"longitude": source.longitude, "latitude": source.latitude}
    return resource


def room_location(source: RoomSource) -> Resource:
    equipment = [extension("room-equipment", "valueString", item) for item in source.equipment]
    return {
        "resourceType": "Location",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "extension": [
            extension("room-floor", "valueString", source.floor),
            extension("room-capacity", "valueInteger", source.capacity),
            *equipment,
        ],
        "status": _status(source.is_active),
        "name": source.name,
        "physicalType": coding(LOCATION_TYPE_SYSTEM, "ro", "Room"),
        "managingOrganization": reference("Organization", source.department_id),
        "partOf": reference("Location", source.hospital_id),
        **code_identifier(source.code),
    }


def _status(is_active: bool) -> str:
    return "active" if is_active else "inactive"
