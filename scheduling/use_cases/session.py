"""Section 12.2: open, resolve, extend and end a session. The token leaves only as the return
value of open_session; the database holds its SHA-256, enough because the token is random."""

import hashlib
import secrets
from dataclasses import dataclass

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.session_rules import extended_expiry, session_lifetime
from scheduling.models import Session, User
from scheduling.models.access import SessionKind
from scheduling.models.people import Role
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.request_context import current_request_context

TOKEN_BYTES = 32
USER_AGENT_LIMIT = 300


@dataclass(frozen=True)
class OpenedSession:
    session: Session
    token: str


@dataclass(frozen=True)
class ResolvedSession:
    session: Session
    user: User
    extended: bool


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(user: User, kind: SessionKind, user_agent: str) -> OpenedSession:
    now = current_request_context().now
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session = Session.objects.create(
        user=user,
        token_hash=hash_token(token),
        opened_by=kind,
        created_at=now,
        expires_at=now + session_lifetime(kind, Role(user.role)),
        user_agent=user_agent[:USER_AGENT_LIMIT],
    )
    return OpenedSession(session, token)


def resolve_session(token: str) -> Result[ResolvedSession]:
    now = current_request_context().now
    session = Session.objects.select_related("user").filter(token_hash=hash_token(token)).first()
    if session is None or session.expires_at <= now or not session.user.is_active:
        return Failure.unauthenticated()
    new_expiry = extended_expiry(
        SessionKind(session.opened_by), Role(session.user.role), session.expires_at, now
    )
    if new_expiry is not None:
        session.expires_at = new_expiry
        session.save(update_fields=["expires_at", "updated_at"])
    return Success(ResolvedSession(session, session.user, new_expiry is not None))


def sign_out(token: str) -> None:
    with transaction.atomic():
        session = (
            Session.objects.select_related("user").filter(token_hash=hash_token(token)).first()
        )
        if session is None:
            return
        session_id = str(session.pk)
        session.delete()
        record_audit(
            AuditEvent("auth.logout", "Session", session_id, AuditMetadata()), session.user
        )
