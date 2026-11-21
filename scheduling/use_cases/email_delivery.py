"""Section 7.6 and 11: mail a patient notification, once it is committed. A failed send leaves
the row pending for the next run of send_pending_emails; delivery is at least once."""

import logging
from smtplib import SMTPException
from uuid import UUID
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.email_content import EmailSubject, patient_email
from scheduling.models import Notification
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.request_context import current_request_context

logger = logging.getLogger(__name__)


def send_pending_emails(limit: int) -> int:
    pending = Notification.objects.filter(email_pending=True).order_by("created_at")
    identifiers = list(pending.values_list("pk", flat=True)[:limit])
    return sum(send_notification_email(identifier) for identifier in identifiers)


def send_notification_email(notification_id: UUID) -> bool:
    """True when the email went out. Never raises for a mail server problem."""
    with transaction.atomic():
        locked = Notification.objects.select_for_update(skip_locked=True, of=("self",))
        notification = (
            locked.select_related("recipient", "appointment__clinician__user")
            .filter(pk=notification_id, email_pending=True)
            .first()
        )
        if notification is None:
            return False
        try:
            _message_of(notification).send()
        except (OSError, SMTPException) as error:
            logger.warning(
                "notification email not sent",
                extra={
                    "notification_id": str(notification.pk),
                    "correlation_id": current_request_context().correlation_id,
                    "error_class": type(error).__name__,
                },
            )
            return False
        notification.email_pending = False
        notification.save(update_fields=["email_pending"])
        metadata = AuditMetadata(
            ids={"notification_id": notification.pk},
            changed_fields=changed_field_names(Notification, ["email_pending"]),
        )
        event = AuditEvent(
            "notification.email_sent", "Notification", str(notification.pk), metadata
        )
        record_audit(event, None)
        return True


def _message_of(notification: Notification) -> EmailMessage:
    appointment = notification.appointment
    if appointment is None:
        raise ValueError("a patient email notification belongs to an appointment")
    hospital = appointment.appointment_type.department.hospital
    text = patient_email(
        EmailSubject(
            title=notification.title,
            starts_at=appointment.starts_at,
            time_zone=ZoneInfo(hospital.time_zone),
            hospital_name=hospital.name,
            provider_name=appointment.clinician.user.full_name,
            sign_in_url=f"{settings.PUBLIC_BASE_URL}/sign-in",
        )
    )
    return EmailMessage(
        subject=text.subject,
        body=text.body,
        from_email=settings.EMAIL_SENDER,
        to=[notification.recipient.email],
    )
