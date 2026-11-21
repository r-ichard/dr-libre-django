"""Task 15: a patient reads and marks only their own notifications; marking is audited."""

import uuid
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, Notification, User
from scheduling.models.builders import make
from scheduling.use_cases.notification_inbox import (
    mark_all_read,
    mark_read,
    notifications_page,
    unread_count,
)
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 3, 15, 9, 0, tzinfo=UTC)


def _patient() -> User:
    user = make("User", role="PATIENT")
    assert isinstance(user, User)
    return user


def _notification(user: User, age_days: int, **overrides: object) -> Notification:
    created = {"created_at": NOW - timedelta(days=age_days)}
    row = make("Notification", recipient=user, title=f"Title {age_days}", **created, **overrides)
    assert isinstance(row, Notification)
    return row


def _bound() -> AbstractContextManager[None]:
    return bind_request_context(RequestContext(correlation_id="corr-1", now=NOW))


def returns_newest_first_and_the_oldest_on_page_two_with_the_total() -> None:
    user = _patient()
    for age in range(1, 13):
        _notification(user, age)

    first = notifications_page(user, 1, 10)
    second = notifications_page(user, 2, 10)

    assert first.total == 12
    assert [row.title for row in first.rows][:2] == ["Title 1", "Title 2"]
    assert [row.title for row in second.rows] == ["Title 11", "Title 12"]


def returns_only_own_notifications_and_own_unread_count() -> None:
    user, other = _patient(), _patient()
    _notification(user, 1)
    _notification(other, 1)
    _notification(other, 2)

    assert notifications_page(user, 1, 10).total == 1
    assert unread_count(user) == 1


def returns_read_time_from_request_clock_and_one_audit_when_marking_one_read() -> None:
    user = _patient()
    row = _notification(user, 1)

    with _bound():
        first = mark_read(row.pk, user)
        second = mark_read(row.pk, user)

    row.refresh_from_db()
    entries = AuditLogEntry.objects.filter(action="notification.read")
    assert isinstance(first, Success) and isinstance(second, Success)
    assert row.read_at == NOW and entries.count() == 1
    assert entries.get().metadata["changed_fields"] == ["read_at"]


def returns_forbidden_and_leaves_the_row_unread_when_the_notification_is_someone_elses() -> None:
    user, other = _patient(), _patient()
    foreign = _notification(other, 1)

    with _bound():
        result = mark_read(foreign.pk, user)

    foreign.refresh_from_db()
    assert isinstance(result, Failure) and result.code == FailureCode.FORBIDDEN
    assert foreign.read_at is None and AuditLogEntry.objects.count() == 0


def returns_not_found_when_the_notification_does_not_exist() -> None:
    with _bound():
        result = mark_read(uuid.uuid4(), _patient())

    assert isinstance(result, Failure) and result.code == FailureCode.NOT_FOUND


def returns_only_own_unread_rows_marked_and_counted_when_marking_all_read() -> None:
    user, other = _patient(), _patient()
    _notification(user, 1)
    _notification(user, 2)
    _notification(user, 3, read_at=NOW - timedelta(days=1))
    foreign = _notification(other, 1)

    with _bound():
        mark_all_read(user)

    foreign.refresh_from_db()
    assert unread_count(user) == 0 and foreign.read_at is None
    entry = AuditLogEntry.objects.get(action="notification.read")
    assert entry.metadata["counts"] == {"notification_count": 2}


def returns_no_audit_entry_when_there_is_nothing_unread() -> None:
    user = _patient()

    with _bound():
        result = mark_all_read(user)

    assert isinstance(result, Success) and AuditLogEntry.objects.count() == 0
