"""Housekeeping: expired sessions and sign-in failure rows older than the lockout window go."""

from dataclasses import dataclass

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.lockout_rules import window_start
from scheduling.models import Session, SignInFailure
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.request_context import current_request_context


@dataclass(frozen=True)
class PurgeCounts:
    session_count: int
    sign_in_failure_count: int


def purge_expired() -> PurgeCounts:
    now = current_request_context().now
    with transaction.atomic():
        session_count, _ = Session.objects.filter(expires_at__lt=now).delete()
        failures = SignInFailure.objects.filter(failed_at__lt=window_start(now))
        failure_count, _ = failures.delete()
        counts = PurgeCounts(session_count, failure_count)
        if session_count or failure_count:
            metadata = AuditMetadata(
                counts={
                    "session_count": session_count,
                    "sign_in_failure_count": failure_count,
                }
            )
            record_audit(
                AuditEvent("housekeeping.purge", "Session", "housekeeping", metadata), None
            )
        return counts
