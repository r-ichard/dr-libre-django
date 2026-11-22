"""Task 15: a patient's own notifications, read and marked as read."""

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, Result, Success
from scheduling.models import Notification, User
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.record_access import guard_record
from scheduling.use_cases.request_context import current_request_context


@dataclass(frozen=True)
class NotificationPage:
    rows: list[Notification]
    total: int


def notifications_page(patient: User, page: int, size: int) -> NotificationPage:
    own = Notification.objects.filter(recipient=patient)
    offset = (page - 1) * size
    newest = own.select_related(
        "appointment__appointment_type__department__hospital",
        "waitlist_entry__appointment_type__department__hospital",
    ).order_by("-created_at", "-id")
    rows = newest[offset : offset + size]
    return NotificationPage(list(rows), own.count())


def unread_count(patient: User) -> int:
    return Notification.objects.filter(recipient=patient, read_at__isnull=True).count()


def mark_read(notification_id: UUID, actor: User) -> Result[None]:
    with transaction.atomic():
        row = Notification.objects.select_for_update().filter(pk=notification_id).first()
        guarded = guard_record(row, lambda found: found.recipient_id == actor.pk)
        if isinstance(guarded, Failure):
            return guarded
        notification = guarded.value
        if notification.read_at is None:
            notification.read_at = current_request_context().now
            notification.save()
            metadata = AuditMetadata(
                ids={"notification_id": notification.pk},
                changed_fields=changed_field_names(Notification, ["read_at"]),
            )
            _audit(notification.pk, metadata, actor)
        return Success(None)


def mark_all_read(actor: User) -> Result[None]:
    with transaction.atomic():
        unread = list(
            Notification.objects.select_for_update().filter(recipient=actor, read_at__isnull=True)
        )
        if not unread:
            return Success(None)
        now = current_request_context().now
        for notification in unread:
            notification.read_at = now
            notification.save()
        metadata = AuditMetadata(
            counts={"notification_count": len(unread)},
            changed_fields=changed_field_names(Notification, ["read_at"]),
        )
        _audit(actor.pk, metadata, actor)
        return Success(None)


def _audit(entity_id: UUID, metadata: AuditMetadata, actor: User) -> None:
    record_audit(AuditEvent("notification.read", "Notification", str(entity_id), metadata), actor)
