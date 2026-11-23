"""The specialty list as one CodeSystem and one ValueSet, spec 15.2."""

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
    inactive_codes: frozenset[str] = frozenset()


INACTIVE_CODE = "inactive"
INACTIVE_DECLARATION: Resource = {
    "code": INACTIVE_CODE,
    "uri": "http://hl7.org/fhir/concept-properties#inactive",
    "type": "boolean",
}


def _concept(source: SpecialtyList, code: str, display: str) -> Resource:
    listed: Resource = {"code": code, "display": display}
    if code in source.inactive_codes:
        listed["property"] = [{"code": INACTIVE_CODE, "valueBoolean": True}]
    return listed


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
        "property": [INACTIVE_DECLARATION],
        "count": len(source.concepts),
        "concept": [_concept(source, code, display) for code, display in source.concepts],
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
