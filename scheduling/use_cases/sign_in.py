"""Section 12.1: password sign-in. Each attempt runs the hasher once, so every failure costs the
same time and gives the same answer. SignInFailure counts failures by HMAC of the address."""

import hashlib
import hmac
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata, email_domain
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.lockout_rules import is_locked, window_start
from scheduling.domain.sign_in_rules import Home, home_for
from scheduling.domain.vocabulary import Role, SessionKind
from scheduling.models import SignInFailure, User
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import OpenedSession, open_session


@dataclass(frozen=True)
class SignedIn:
    home: Home
    opened: OpenedSession


def hash_email(email: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, email.lower().encode(), hashlib.sha256).hexdigest()


def sign_in_with_password(email: str, password: str, user_agent: str) -> Result[SignedIn]:
    now = current_request_context().now
    email_key = hash_email(email)
    domain_metadata = AuditMetadata(email_domain=email_domain(email))
    with transaction.atomic():
        user = User.objects.filter(email=email.lower()).first()
        recent = SignInFailure.objects.filter(email_hash=email_key, failed_at__gt=window_start(now))
        failure_count = recent.count()
        password_matches = _run_hasher_once(user, password)
        if is_locked(failure_count):
            newest = recent.order_by("-failed_at", "-id")[0]
            lockout_metadata = AuditMetadata(
                email_domain=domain_metadata.email_domain, counts={"failure_count": failure_count}
            )
            _audit("auth.lockout", "SignInFailure", str(newest.pk), user, lockout_metadata)
        elif user is None or not user.is_active or not password_matches:
            _record_failure(email_key, user, domain_metadata)
        else:
            SignInFailure.objects.filter(email_hash=email_key).delete()
            opened = open_session(user, SessionKind.PASSWORD, user_agent)
            _audit("auth.login", "Session", str(opened.session.pk), user, domain_metadata)
            return Success(SignedIn(home_for(Role(user.role)), opened))
    return Failure.unauthenticated()


def _run_hasher_once(user: User | None, password: str) -> bool:
    if user is not None and user.has_usable_password():
        return check_password(password, user.password)
    make_password(password)
    return False


def _record_failure(email_key: str, user: User | None, metadata: AuditMetadata) -> None:
    now = current_request_context().now
    SignInFailure.objects.filter(email_hash=email_key, failed_at__lte=window_start(now)).delete()
    failure = SignInFailure.objects.create(email_hash=email_key, failed_at=now)
    _audit("auth.login_failed", "SignInFailure", str(failure.pk), user, metadata)


def _audit(
    action: str, entity_type: str, entity_id: str, user: User | None, metadata: AuditMetadata
) -> None:
    record_audit(AuditEvent(action, entity_type, entity_id, metadata), user)


def is_locked_out(email: str) -> bool:
    """For the sign-in page, asked only after a failure: tells lockout from a wrong password."""
    now = current_request_context().now
    recent = SignInFailure.objects.filter(
        email_hash=hash_email(email), failed_at__gt=window_start(now)
    )
    return is_locked(recent.count())
