"""Task 22, spec 15.2: the specialty list as one CodeSystem and one ValueSet."""

from dataclasses import dataclass
from datetime import datetime

from scheduling.domain.fhir_common import (
    SPECIALTY_ID,
    SPECIALTY_SYSTEM,
    SPECIALTY_VALUE_SET,
    Resource,
    meta,
)


@dataclass(frozen=True)
class SpecialtyList:
    version: int
    updated_at: datetime
    concepts: tuple[tuple[str, str], ...]


def specialty_code_system(source: SpecialtyList) -> Resource:
    return {
        "resourceType": "CodeSystem",
        "id": SPECIALTY_ID,
        "meta": meta(source.version, source.updated_at),
        "url": SPECIALTY_SYSTEM,
        "name": "DrLibreSpecialty",
        "status": "active",
        "content": "complete",
        "caseSensitive": False,
        "count": len(source.concepts),
        "concept": [{"code": code, "display": display} for code, display in source.concepts],
    }


def specialty_value_set(source: SpecialtyList) -> Resource:
    return {
        "resourceType": "ValueSet",
        "id": SPECIALTY_ID,
        "meta": meta(source.version, source.updated_at),
        "url": SPECIALTY_VALUE_SET,
        "name": "DrLibreSpecialty",
        "status": "active",
        "compose": {"include": [{"system": SPECIALTY_SYSTEM}]},
    }
