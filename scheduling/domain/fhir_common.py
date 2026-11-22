"""Task 22, spec 15: the names and small builders every FHIR mapper shares."""

from datetime import UTC, datetime
from uuid import UUID

CANONICAL_BASE = "https://drlibre.example/fhir"
FHIR_VERSION = "4.0.1"
SPECIALTY_ID = "specialty"
SPECIALTY_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/{SPECIALTY_ID}"
SPECIALTY_VALUE_SET = f"{CANONICAL_BASE}/ValueSet/{SPECIALTY_ID}"
ORGANIZATION_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/organization-type"
LOCATION_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/location-physical-type"

CODE_IDENTIFIER_SYSTEM = f"{CANONICAL_BASE}/identifier/code"

type Resource = dict[str, object]


def extension_url(name: str) -> str:
    return f"{CANONICAL_BASE}/StructureDefinition/{name}"


def extension(name: str, value_key: str, value: object) -> Resource:
    return {"url": extension_url(name), value_key: value}


def fhir_instant(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def meta(version: int, updated_at: datetime) -> Resource:
    return {"versionId": str(version), "lastUpdated": fhir_instant(updated_at)}


def reference(resource_type: str, identifier: UUID) -> Resource:
    return {"reference": f"{resource_type}/{identifier}"}


def code_identifier(code: str) -> Resource:
    """The record's unique code, which a client reads and sends back; none when not loaded."""
    if not code:
        return {}
    return {"identifier": [{"system": CODE_IDENTIFIER_SYSTEM, "value": code}]}


def coding(system: str, code: str, display: str) -> Resource:
    return {"coding": [{"system": system, "code": code, "display": display}]}
