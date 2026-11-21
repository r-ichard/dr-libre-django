"""Sections 7.1 and 7.7: removing a hold frees its slot. The job of the worker removes expired
holds one by one, each with its own audit entry."""

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata, email_domain
from scheduling.models import BookingHold, VerificationCode
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.request_context import current_request_context

EXPIRED_ACTION = "booking_hold.expired"


def remove_hold(hold: BookingHold, action: str) -> None:
    """Inside the caller's transaction. The actor is empty: nobody has verified an email yet."""
    VerificationCode.objects.filter(hold=hold).delete()
    metadata = AuditMetadata(
        ids={"clinician_id": hold.clinician_id}, email_domain=email_domain(hold.visitor_email)
    )
    record_audit(AuditEvent(action, "BookingHold", str(hold.pk), metadata), None)
    hold.delete()


def expire_booking_holds() -> int:
    now = current_request_context().now
    with transaction.atomic():
        expired = BookingHold.objects.select_for_update(skip_locked=True).filter(
            expires_at__lte=now
        )
        holds = list(expired)
        for hold in holds:
            remove_hold(hold, EXPIRED_ACTION)
    return len(holds)
