"""Section 5.7: one reminder for each appointment starting within 24 hours, never twice."""

from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, QuerySet

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.waitlist_rules import REMINDED_STATUSES, REMINDER_LEAD
from scheduling.models import Appointment, Notification, User
from scheduling.models.booking import NotificationKind
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.notifications import REMINDER_TITLE, notify_patient
from scheduling.use_cases.request_context import current_request_context

REMINDER_ONCE_CONSTRAINT = "notification_one_reminder_per_appointment"


def _due_appointments(now: datetime) -> QuerySet[Appointment]:
    already_reminded = Notification.objects.filter(
        appointment=OuterRef("pk"), kind=NotificationKind.APPOINTMENT_REMINDER
    )
    return Appointment.objects.filter(
        ~Exists(already_reminded),
        status__in=REMINDED_STATUSES,
        starts_at__gt=now,
        starts_at__lte=now + REMINDER_LEAD,
    )


def send_reminders(actor: User | None) -> int:
    now = current_request_context().now
    with transaction.atomic():
        # Skipping locked rows covers runs overlapping in time; the unique constraint covers a
        # run whose candidate list predates the other run's commit.
        candidates = _due_appointments(now).select_for_update(skip_locked=True, of=("self",))
        reminded = sum(
            _remind(appointment)
            for appointment in candidates.select_related("appointment_type__department__hospital")
        )
        if reminded:
            metadata = AuditMetadata(counts={"reminder_count": reminded})
            record_audit(AuditEvent("reminder.run", "Notification", "reminders", metadata), actor)
        return reminded


def _remind(appointment: Appointment) -> bool:
    try:
        with transaction.atomic():
            notify_patient(appointment, NotificationKind.APPOINTMENT_REMINDER, REMINDER_TITLE)
    except IntegrityError as error:
        if REMINDER_ONCE_CONSTRAINT not in str(error):
            raise
        return False
    return True
