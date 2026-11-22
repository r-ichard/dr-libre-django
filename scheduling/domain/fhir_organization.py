"""Task 22, spec 15.2: a hospital and a department as an Organization."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.fhir_common import (
    ORGANIZATION_TYPE_SYSTEM,
    Resource,
    coding,
    meta,
    reference,
)


@dataclass(frozen=True)
class OrganizationSource:
    id: UUID
    name: str
    version: int
    updated_at: datetime
    is_active: bool
    hospital_id: UUID | None


def hospital_organization(source: OrganizationSource) -> Resource:
    return _organization(source, "prov", "Healthcare Provider")


def department_organization(source: OrganizationSource) -> Resource:
    resource = _organization(source, "dept", "Hospital Department")
    if source.hospital_id is not None:
        resource["partOf"] = reference("Organization", source.hospital_id)
    return resource


def _organization(source: OrganizationSource, code: str, display: str) -> Resource:
    return {
        "resourceType": "Organization",
        "id": str(source.id),
        "meta": meta(source.version, source.updated_at),
        "active": source.is_active,
        "type": [coding(ORGANIZATION_TYPE_SYSTEM, code, display)],
        "name": source.name,
    }
