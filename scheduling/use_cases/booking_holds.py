"""Section 7.1 steps 3 and 4, 7.5, 7.7: hold a slot for a visitor and send the code, or send a
new code. Nothing here reads an account: the same request gives the same answer and the same work
for a new address, a patient and a staff address."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata, email_domain
from scheduling.domain.booking_codes import HOLD_LIFETIME
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.domain.visitor_rules import normalise_email, valid_birth_date
from scheduling.models import BookingHold
from scheduling.models.access import HoldSource
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.booking_codes import issue_code
from scheduling.use_cases.hold_expiry import EXPIRED_ACTION, remove_hold
from scheduling.use_cases.placement import PlacementCommand, probe_placement
from scheduling.use_cases.rate_limits import take_hit
from scheduling.use_cases.request_context import current_request_context

REPLACED_ACTION = "booking_hold.replaced"


@dataclass(frozen=True)
class HoldCommand:
    appointment_type_id: UUID
    clinician_id: UUID | None
    starts_at: datetime
    full_name: str
    birth_date: date
    email: str
    phone: str
    reason: str
    terms_accepted: bool


def create_hold(command: HoldCommand, address: str) -> Result[BookingHold]:
    """A second hold for the same email replaces the first: a visitor who changed their mind or
    lost the page is not locked out for ten minutes."""
    now = current_request_context().now
    invalid = _invalid_input(command, now)
    if invalid is not None:
        return invalid
    email = normalise_email(command.email)
    with transaction.atomic():
        if not take_hit(RateLimitScope.HOLD, email, address):
            return Failure.rate_limited()
        earlier = BookingHold.objects.select_for_update().filter(visitor_email=email).first()
        probe = probe_placement(
            PlacementCommand(
                command.appointment_type_id, command.starts_at, command.clinician_id, None, None
            ),
            earlier.pk if earlier is not None else None,
        )
        if isinstance(probe, Failure):
            return probe
        if earlier is not None:
            action = EXPIRED_ACTION if earlier.expires_at <= now else REPLACED_ACTION
            remove_hold(earlier, action)
        source = HoldSource.ONLINE if command.clinician_id else HoldSource.ROUND_ROBIN
        hold = BookingHold.objects.create(
            clinician=probe.value.clinician,
            appointment_type_id=command.appointment_type_id,
            starts_at=command.starts_at,
            ends_at=probe.value.ends_at,
            source=source,
            visitor_name=command.full_name,
            visitor_birth_date=command.birth_date,
            visitor_email=email,
            visitor_phone=command.phone,
            visitor_reason=command.reason,
            expires_at=now + HOLD_LIFETIME,
            terms_accepted_at=now,
        )
        sent = issue_code(hold)
        if isinstance(sent, Failure):
            transaction.set_rollback(True)
            return sent
        metadata = AuditMetadata(
            ids={"clinician_id": hold.clinician_id}, email_domain=email_domain(email)
        )
        record_audit(
            AuditEvent("booking_hold.created", "BookingHold", str(hold.pk), metadata), None
        )
        return Success(hold)


def resend_code(hold_id: UUID, address: str) -> Result[BookingHold]:
    now = current_request_context().now
    with transaction.atomic():
        known = BookingHold.objects.filter(pk=hold_id, expires_at__gt=now).first()
        if known is None:
            return Failure.not_found()
        # The counter lock comes before the hold's row lock, as in create_hold.
        if not take_hit(RateLimitScope.CODE, known.visitor_email, address):
            return Failure.rate_limited()
        locked = BookingHold.objects.select_for_update().filter(pk=hold_id).first()
        if locked is None:
            return Failure.not_found()
        sent = issue_code(locked)
        if isinstance(sent, Failure):
            transaction.set_rollback(True)
            return sent
        return Success(locked)


def _invalid_input(command: HoldCommand, now: datetime) -> Failure | None:
    problems = []
    if not command.terms_accepted:
        problems.append(FieldMessage("terms_accepted", "Accept the terms and the privacy notice."))
    if not valid_birth_date(command.birth_date, now.date()):
        problems.append(FieldMessage("birth_date", "Enter a valid date of birth."))
    try:
        email_domain(normalise_email(command.email))
    except ValueError:
        problems.append(FieldMessage("email", "Enter a valid email address."))
    return Failure.invalid_input(problems) if problems else None
