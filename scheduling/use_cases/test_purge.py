"""Housekeeping: expired sessions and sign-in failure rows older than the lockout window go."""

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

from scheduling.domain.lockout_rules import LOCKOUT_WINDOW
from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, Session, SignInFailure
from scheduling.models.builders import make, unique_hash
from scheduling.use_cases.purge import PurgeCounts, purge_expired
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import NOW

pytestmark = pytest.mark.django_db

ONE_SECOND = timedelta(seconds=1)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-purge", NOW)):
        yield


def returns_expired_session_deleted_when_purged() -> None:
    expired = make("Session", expires_at=NOW - ONE_SECOND)

    counts = purge_expired()

    assert counts == PurgeCounts(session_count=1, sign_in_failure_count=0, rate_limit_hit_count=0)
    assert not Session.objects.filter(pk=expired.pk).exists()


def returns_session_kept_when_it_expires_exactly_now() -> None:
    session = make("Session", expires_at=NOW)

    assert purge_expired().session_count == 0
    assert Session.objects.filter(pk=session.pk).exists()


def returns_session_kept_when_it_expires_in_the_future() -> None:
    session = make("Session", expires_at=NOW + ONE_SECOND)

    purge_expired()

    assert Session.objects.filter(pk=session.pk).exists()


def returns_failure_row_deleted_when_older_than_the_lockout_window() -> None:
    old = make("SignInFailure", failed_at=NOW - LOCKOUT_WINDOW - ONE_SECOND)

    counts = purge_expired()

    assert counts == PurgeCounts(session_count=0, sign_in_failure_count=1, rate_limit_hit_count=0)
    assert not SignInFailure.objects.filter(pk=old.pk).exists()


def returns_failure_row_kept_when_exactly_at_the_lockout_window_start() -> None:
    boundary = make("SignInFailure", failed_at=NOW - LOCKOUT_WINDOW)

    assert purge_expired().sign_in_failure_count == 0
    assert SignInFailure.objects.filter(pk=boundary.pk).exists()


def returns_failure_row_kept_when_inside_the_lockout_window() -> None:
    fresh = make("SignInFailure", failed_at=NOW - timedelta(minutes=1))

    purge_expired()

    assert SignInFailure.objects.filter(pk=fresh.pk).exists()


def returns_audit_entry_with_both_counts_when_rows_were_purged() -> None:
    make("Session", expires_at=NOW - ONE_SECOND)
    make("Session", expires_at=NOW - ONE_SECOND)
    make("SignInFailure", failed_at=NOW - LOCKOUT_WINDOW - ONE_SECOND)

    purge_expired()

    audit = AuditLogEntry.objects.get(action="housekeeping.purge")
    assert audit.actor_id is None
    assert audit.metadata["counts"] == {
        "session_count": 2,
        "sign_in_failure_count": 1,
        "rate_limit_hit_count": 0,
    }


def returns_no_audit_entry_when_nothing_was_purged() -> None:
    make("Session", expires_at=NOW + ONE_SECOND)

    assert purge_expired() == PurgeCounts(
        session_count=0, sign_in_failure_count=0, rate_limit_hit_count=0
    )
    assert AuditLogEntry.objects.filter(action="housekeeping.purge").count() == 0


def returns_audit_entry_when_only_failure_rows_were_purged() -> None:
    make("SignInFailure", failed_at=NOW - LOCKOUT_WINDOW - ONE_SECOND)

    purge_expired()

    audit = AuditLogEntry.objects.get(action="housekeeping.purge")
    assert audit.metadata["counts"] == {
        "session_count": 0,
        "sign_in_failure_count": 1,
        "rate_limit_hit_count": 0,
    }


def returns_audit_entry_when_only_sessions_were_purged() -> None:
    make("Session", expires_at=NOW - ONE_SECOND)

    purge_expired()

    audit = AuditLogEntry.objects.get(action="housekeeping.purge")
    assert audit.metadata["counts"] == {
        "session_count": 1,
        "sign_in_failure_count": 0,
        "rate_limit_hit_count": 0,
    }


def _hit(hit_at: datetime) -> object:
    from django.apps import apps

    return apps.get_model("scheduling", "RateLimitHit").objects.create(
        scope="hold", key_hash=unique_hash(), hit_at=hit_at
    )


def returns_rate_limit_hit_deleted_when_older_than_an_hour() -> None:
    old = _hit(NOW - timedelta(hours=1) - ONE_SECOND)

    counts = purge_expired()

    assert counts.rate_limit_hit_count == 1
    assert not type(old).objects.filter(pk=old.pk).exists()  # type: ignore[attr-defined]


def returns_rate_limit_hit_kept_when_exactly_an_hour_old() -> None:
    boundary = _hit(NOW - timedelta(hours=1))

    assert purge_expired().rate_limit_hit_count == 0
    assert type(boundary).objects.filter(pk=boundary.pk).exists()  # type: ignore[attr-defined]
