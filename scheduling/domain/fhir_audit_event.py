"""Task 24, spec 4, 15.2, 15.5: an audit log entry as an `AuditEvent`. The metadata holds only ids,
counts, status values, field names and an email domain (section 4), so each key becomes one
`entity.detail` and nothing else of a person can appear."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from scheduling.domain.audit_metadata import METADATA_KEYS
from scheduling.domain.fhir_audit_action import audit_action_code
from scheduling.domain.fhir_common import CANONICAL_BASE, Resource, extension, fhir_instant, meta

AUDIT_EVENT_TYPE = "AuditEvent"
ENTITY_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/audit-entity-type"
ACTION_SYSTEM = f"{CANONICAL_BASE}/CodeSystem/audit-action"
CORRELATION_EXTENSION = "correlation-id"


@dataclass(frozen=True)
class AuditFacts:
    id: UUID
    version: int
    updated_at: datetime
    recorded_at: datetime
    action: str
    actor_type: str | None
    actor_id: UUID | None
    entity_type: str
    entity_id: str
    metadata: dict[str, object]
    correlation_id: str


def audit_event_resource(facts: AuditFacts) -> Resource:
    agent: Resource = {"requestor": True}
    if facts.actor_id is not None and facts.actor_type is not None:
        agent["who"] = {"reference": f"{facts.actor_type}/{facts.actor_id}"}
    entity: Resource = {
        "what": {"identifier": {"system": ENTITY_SYSTEM, "value": facts.entity_id}},
        "type": {"system": ENTITY_SYSTEM, "code": facts.entity_type},
    }
    details = _details(facts.metadata)
    if details:
        entity["detail"] = details
    return {
        "resourceType": AUDIT_EVENT_TYPE,
        "id": str(facts.id),
        "meta": meta(facts.version, facts.updated_at),
        "type": {"system": ACTION_SYSTEM, "code": facts.action},
        "action": audit_action_code(facts.action),
        "recorded": fhir_instant(facts.recorded_at),
        "agent": [agent],
        "source": {"observer": {"display": "DrLibre"}},
        "entity": [entity],
        "extension": [extension(CORRELATION_EXTENSION, "valueString", facts.correlation_id)],
    }


def _details(metadata: dict[str, object]) -> list[Resource]:
    pairs: list[tuple[str, object]] = []
    for key, value in metadata.items():
        if key not in METADATA_KEYS:
            continue
        if isinstance(value, dict):
            pairs += value.items()
        else:
            pairs.append((key, value))
    return [
        {"type": name, "valueString": _text(value)}
        for name, value in pairs
        if value not in (None, [])
    ]


def _text(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
