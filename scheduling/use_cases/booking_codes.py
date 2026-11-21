"""Sections 7.1 step 4 and 7.6: make a booking code, keep only a keyed hash, mail it. The mail goes
out inside the caller's transaction: the visitor must get the code at once, so a mail server that
is down fails the request and nothing is held."""

import hashlib
import hmac
import secrets
from uuid import UUID

from django.conf import settings
from django.core.mail import EmailMessage

from scheduling.domain.booking_codes import CODE_DIGITS, CODE_LIFETIME
from scheduling.domain.email_content import verification_code_email
from scheduling.models import BookingHold, VerificationCode
from scheduling.models.access import CodePurpose
from scheduling.use_cases.request_context import current_request_context

MINUTE_SECONDS = 60


def hash_code(hold_id: UUID, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"booking-code:{hold_id}:{code}".encode(), hashlib.sha256).hexdigest()


def code_matches(stored_hash: str, hold_id: UUID, code: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_code(hold_id, code))


def issue_code(hold: BookingHold) -> None:
    """Replaces any earlier code of the hold, so the earlier one stops working, then mails it."""
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    expires_at = current_request_context().now + CODE_LIFETIME
    VerificationCode.objects.update_or_create(
        hold=hold,
        defaults={
            "code_hash": hash_code(hold.pk, code),
            "email": hold.visitor_email,
            "purpose": CodePurpose.BOOKING,
            "expires_at": expires_at,
            "attempts_used": 0,
        },
    )
    text = verification_code_email(code, int(CODE_LIFETIME.total_seconds() // MINUTE_SECONDS))
    message = EmailMessage(
        subject=text.subject,
        body=text.body,
        from_email=settings.EMAIL_SENDER,
        to=[hold.visitor_email],
    )
    message.send()
