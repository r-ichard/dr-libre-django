"""Section 4: the one way a use case records an AuditLogEntry, inside the change's transaction."""

from collections.abc import Iterable
from dataclasses import dataclass

from django.db import connection
from django.db.models import Model

from scheduling.domain.audit_metadata import AuditMetadata, FieldName, field_name
from scheduling.models import AuditLogEntry, User
from scheduling.use_cases.request_context import current_request_context


class TransactionRequired(Exception):  # noqa: N818 - name fixed by the published contract tests
    """An audit entry written outside the transaction of its change is a broken invariant."""


@dataclass(frozen=True)
class AuditEvent:
    action: str
    entity_type: str
    entity_id: str
    metadata: AuditMetadata


def record_audit(event: AuditEvent, actor: User | None) -> None:
    if not connection.in_atomic_block:
        raise TransactionRequired("record_audit must run inside transaction.atomic")
    context = current_request_context()
    AuditLogEntry.objects.create(
        actor=actor,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        metadata=event.metadata.to_json(),
        correlation_id=context.correlation_id,
        created_at=context.now,
    )


def changed_field_names(model_class: type[Model], names: Iterable[str]) -> tuple[FieldName, ...]:
    requested = tuple(names)
    concrete = {model_field.name for model_field in model_class._meta.concrete_fields}
    unknown = [name for name in requested if name not in concrete]
    if unknown:
        raise ValueError(f"{model_class.__name__} has no field {unknown[0]}")
    return tuple(field_name(name) for name in requested)
