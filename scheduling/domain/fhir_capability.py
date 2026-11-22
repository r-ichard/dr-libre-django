"""Task 22, spec 15.1: the CapabilityStatement, built from the declaration that routes the
resources, so it cannot name what is not served."""

from collections.abc import Sequence

from scheduling.domain.fhir_common import FHIR_VERSION, Resource
from scheduling.domain.fhir_declaration import (
    FHIR_TYPE_OF_KIND,
    INTERACTIONS,
    ResourceDeclaration,
)

CAPABILITY_DATE = "2026-11-22"


def capability_statement(declarations: Sequence[ResourceDeclaration]) -> Resource:
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": CAPABILITY_DATE,
        "kind": "instance",
        "fhirVersion": FHIR_VERSION,
        "format": ["application/fhir+json"],
        "rest": [
            {"mode": "server", "resource": [_resource(item) for item in declarations]},
        ],
    }


def _resource(declaration: ResourceDeclaration) -> Resource:
    resource: Resource = {
        "type": declaration.type,
        "versioning": "versioned",
        "interaction": [{"code": code} for code in INTERACTIONS],
        "searchParam": [
            {"name": item.name, "type": FHIR_TYPE_OF_KIND[item.kind]}
            for item in declaration.parameters
        ],
    }
    if declaration.includes:
        resource["searchInclude"] = list(declaration.includes)
    return resource
