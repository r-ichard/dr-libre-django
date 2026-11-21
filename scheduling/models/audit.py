from django.db.models import PROTECT, CharField, ForeignKey, JSONField

from scheduling.models.base import Versioned, not_blank
from scheduling.models.people import User


class AuditLogEntry(Versioned):
    """Append-only: a database trigger (migration 0002) refuses update, delete and truncate."""

    fhir_resources = ("AuditEvent",)

    actor = ForeignKey(User, null=True, blank=True, on_delete=PROTECT)
    action = CharField(max_length=100)
    entity_type = CharField(max_length=100)
    entity_id = CharField(max_length=64)
    metadata = JSONField(default=dict)
    correlation_id = CharField(max_length=100)

    class Meta:
        verbose_name_plural = "audit log entries"
        constraints = [
            not_blank("auditlogentry", "action"),
            not_blank("auditlogentry", "entity_type"),
            not_blank("auditlogentry", "entity_id"),
            not_blank("auditlogentry", "correlation_id"),
        ]
