"""Section 11: one Notification per event of the table, made in the event's transaction. The
email goes out only after that transaction commits."""

import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import transaction

from scheduling.domain.placement_rules import booked_notification_text
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, Notification, WaitlistEntry
from scheduling.models.booking import NotificationKind
from scheduling.use_cases.email_delivery import send_notification_email
from scheduling.use_cases.request_context import bind_request_context, current_request_context

logger = logging.getLogger(__name__)

BOOKED_TITLE = "Appointment booked"
CANCELLED_TITLE = "Appointment cancelled"
RESCHEDULED_TITLE = "Appointment rescheduled"
REMINDER_TITLE = "Appointment reminder"
OFFERED_TITLE = "Waitlist slot offered"
WAITLIST_BOOKED_TITLE = "Waitlist slot booked"


def notify_patient(appointment: Appointment, kind: NotificationKind, title: str) -> None:
    hospital = appointment.appointment_type.department.hospital
    _notify(
        Notification(
            recipient_id=appointment.patient_id,
            kind=kind,
            title=title,
            body=booked_notification_text(appointment.starts_at, ZoneInfo(hospital.time_zone)),
            appointment=appointment,
        )
    )


def notify_waitlist_patient(
    entry: WaitlistEntry, kind: NotificationKind, title: str, starts_at: datetime
) -> None:
    """The row links the entry, and an appointment only when it is the patient's own. The freed
    appointment of another patient is never linked."""
    hospital = entry.appointment_type.department.hospital
    _notify(
        Notification(
            recipient_id=entry.patient_id,
            kind=kind,
            title=title,
            body=booked_notification_text(starts_at, ZoneInfo(hospital.time_zone)),
            waitlist_entry=entry,
            appointment=Appointment.objects.filter(waitlist_entry=entry).first(),
        )
    )


def _notify(notification: Notification) -> None:
    notification.email_pending = True
    notification.save(force_insert=True)
    context = current_request_context()
    transaction.on_commit(lambda: _send_in_context(notification.pk, context))


def _send_in_context(notification_id: UUID, context: RequestContext) -> None:
    # The callback may run after the request unbound its context; the log needs the correlation id.
    with bind_request_context(context):
        try:
            send_notification_email(notification_id)
        except Exception:
            # The change already committed; its answer must not turn into an error.
            logger.exception(
                "notification email lookup failed",
                extra={
                    "notification_id": str(notification_id),
                    "correlation_id": context.correlation_id,
                },
            )
