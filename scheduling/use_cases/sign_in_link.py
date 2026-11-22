"""Section 7.3: sign in by email link, Patient only. Asking takes the same steps for every
address and only a Patient also gets one INSERT; the mail goes out after commit through a pool,
off the request path. Using a link locks only the link row."""

import secrets
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata, EmailDomain, email_domain
from scheduling.domain.email_content import sign_in_link_email
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.domain.sign_in_link_rules import LINK_LIFETIME, TOKEN_BYTES, link_is_usable
from scheduling.domain.visitor_rules import is_valid_email, normalise_email
from scheduling.domain.vocabulary import Role, SessionKind
from scheduling.identifiers import new_identifier
from scheduling.models import SignInLink, User
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.background_mail import send_after_commit
from scheduling.use_cases.rate_limits import take_hit
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import OpenedSession, hash_token, open_session

MINUTE_SECONDS = 60
ENTITY_TYPE = "SignInLink"
REFUSED_MESSAGE = "This sign-in link has expired or was already used."
REFUSAL = Failure.invalid_input([FieldMessage("token", REFUSED_MESSAGE)])


def ask_for_link(email: str, address: str) -> Result[None]:
    normalised = normalise_email(email)
    if not is_valid_email(normalised):
        return Failure.invalid_input([FieldMessage("email", "Enter a valid email address.")])
    domain = email_domain(normalised)
    now = current_request_context().now
    link_id = new_identifier()
    with transaction.atomic():
        wait = take_hit(RateLimitScope.LINK, normalised, address)
        if wait is not None:
            _audit("auth.link_refused", link_id, domain, None)
            return Failure.rate_limited(wait)
        user = User.objects.filter(email=normalised).first()
        token = secrets.token_urlsafe(TOKEN_BYTES)
        SignInLink.objects.filter(
            patient__email=normalised, used_at__isnull=True, cancelled_at__isnull=True
        ).update(cancelled_at=now, updated_at=now)
        if user is not None and user.role == Role.PATIENT and user.is_active:
            SignInLink.objects.create(
                id=link_id,
                token_hash=hash_token(token),
                patient=user,
                expires_at=now + LINK_LIFETIME,
            )
            send_after_commit(_message_of(normalised, token))
        _audit("auth.link_requested", link_id, domain, None)
    return Success(None)


def use_link(token: str, user_agent: str) -> Result[OpenedSession]:
    now = current_request_context().now
    with transaction.atomic():
        link = (
            SignInLink.objects.select_for_update(of=("self",))
            .select_related("patient")
            .filter(token_hash=hash_token(token))
            .first()
        )
        if link is None or not _usable(link, now):
            _audit_refused_use(link)
            return REFUSAL
        link.used_at = now
        link.save(update_fields=["used_at", "updated_at"])
        opened = open_session(link.patient, SessionKind.EMAIL_LINK, user_agent)
        _audit("auth.link_used", link.pk, email_domain(link.patient.email), link.patient)
        return Success(opened)


def _audit_refused_use(link: SignInLink | None) -> None:
    if link is None:
        _audit("auth.link_refused", new_identifier(), None, None)
    else:
        _audit("auth.link_refused", link.pk, email_domain(link.patient.email), None)


def _usable(link: SignInLink, now: datetime) -> bool:
    patient = link.patient
    return (
        link_is_usable(now, link.expires_at, link.used_at, link.cancelled_at)
        and patient.role == Role.PATIENT
        and patient.is_active
    )


def _audit(action: str, entity_id: UUID, domain: EmailDomain | None, actor: User | None) -> None:
    metadata = AuditMetadata(email_domain=domain)
    record_audit(AuditEvent(action, ENTITY_TYPE, str(entity_id), metadata), actor)


def _message_of(email: str, token: str) -> EmailMessage:
    url = f"{settings.PUBLIC_BASE_URL}/sign-in/link?token={token}"
    text = sign_in_link_email(url, int(LINK_LIFETIME.total_seconds() // MINUTE_SECONDS))
    return EmailMessage(
        subject=text.subject, body=text.body, from_email=settings.EMAIL_SENDER, to=[email]
    )
