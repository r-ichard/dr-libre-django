"""Section 12.1: change password; a wrong current password is a failed sign-in for lockout."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from django.contrib.auth.hashers import check_password, make_password

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.lockout_rules import LOCKOUT_FAILURES
from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import AuditLogEntry, Session, SignInFailure, User
from scheduling.models.builders import make
from scheduling.use_cases.profile import change_password
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.use_cases.sign_in import sign_in_with_password

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 3, 15, 9, 0, tzinfo=UTC)
CURRENT = "current-password-1"
NEW = "a-brand-new-password"


def _patient(password: str | None = CURRENT) -> User:
    fields: dict[str, object] = {"role": "PATIENT"}
    fields["password"] = make_password(password)
    if password is None:
        fields["email_verified_at"] = NOW
    user = make("User", **fields)
    assert isinstance(user, User)
    return user


def _change(user: User, current: str, new: str, keep: UUID | None = None) -> object:
    with bind_request_context(RequestContext(correlation_id="corr-1", now=NOW)):
        return change_password(current, new, user, keep)


def _field_of(result: object) -> list[str]:
    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT
    return [item["field"] for item in result.details["fields"]]  # type: ignore[attr-defined]


def returns_new_password_and_only_current_session_left_when_current_is_right() -> None:
    user = _patient()
    with bind_request_context(RequestContext(correlation_id="c", now=NOW)):
        kept = open_session(user, SessionKind.PASSWORD, "agent").session
        open_session(user, SessionKind.PASSWORD, "other")

    result = _change(user, CURRENT, NEW, kept.pk)

    user.refresh_from_db()
    assert isinstance(result, Success) and check_password(NEW, user.password)
    assert [row.pk for row in Session.objects.filter(user=user)] == [kept.pk]


def returns_password_change_audit_with_session_count_and_no_password_or_hash() -> None:
    user = _patient()
    with bind_request_context(RequestContext(correlation_id="c", now=NOW)):
        kept = open_session(user, SessionKind.PASSWORD, "agent").session
        open_session(user, SessionKind.PASSWORD, "other")

    _change(user, CURRENT, NEW, kept.pk)

    entry = AuditLogEntry.objects.get(action="auth.password_change")
    user.refresh_from_db()
    assert entry.metadata["counts"] == {"session_count": 1}
    assert NEW not in str(entry.metadata) and user.password not in str(entry.metadata)


def returns_invalid_input_on_current_password_and_records_a_failure_when_current_is_wrong() -> None:
    user = _patient()

    result = _change(user, "not-the-password", NEW)

    user.refresh_from_db()
    assert _field_of(result) == ["current_password"]
    assert check_password(CURRENT, user.password)
    assert SignInFailure.objects.count() == 1
    failed_entry = AuditLogEntry.objects.get(action="auth.login_failed")
    assert failed_entry.actor == user


def returns_sign_in_locked_when_the_tenth_wrong_current_password_is_entered() -> None:
    user = _patient()
    for _ in range(LOCKOUT_FAILURES):
        _change(user, "not-the-password", NEW)

    with bind_request_context(RequestContext(correlation_id="c", now=NOW)):
        signed_in = sign_in_with_password(user.email, CURRENT, "agent")

    assert isinstance(signed_in, Failure)


def returns_failure_for_the_right_current_password_while_the_address_is_locked() -> None:
    user = _patient()
    for _ in range(LOCKOUT_FAILURES):
        _change(user, "not-the-password", NEW)

    result = _change(user, CURRENT, NEW)

    user.refresh_from_db()
    assert _field_of(result) == ["current_password"]
    assert check_password(CURRENT, user.password)
    assert SignInFailure.objects.count() == LOCKOUT_FAILURES


@pytest.mark.parametrize("new", [CURRENT, "n" * 9, "n" * 73])
def returns_invalid_input_on_new_password_when_it_breaks_the_rules(new: str) -> None:
    user = _patient()

    result = _change(user, CURRENT, new)

    user.refresh_from_db()
    assert _field_of(result) == ["new_password"]
    assert check_password(CURRENT, user.password)


def returns_forbidden_and_writes_nothing_when_the_patient_has_no_password() -> None:
    user = _patient(password=None)

    result = _change(user, "", NEW)

    assert isinstance(result, Failure) and result.code == FailureCode.FORBIDDEN
    assert SignInFailure.objects.count() == 0 and AuditLogEntry.objects.count() == 0


def _messages_of(result: object) -> dict[str, str]:
    assert isinstance(result, Failure)
    return {item["field"]: item["message"] for item in result.details["fields"]}  # type: ignore[attr-defined]


def returns_enter_message_and_no_lockout_failure_when_current_password_is_empty() -> None:
    user = _patient()

    result = _change(user, "", NEW)

    assert _messages_of(result) == {"current_password": "Enter your current password."}
    assert SignInFailure.objects.count() == 0


def returns_both_enter_messages_when_current_and_new_password_are_empty() -> None:
    user = _patient()

    result = _change(user, "", "")

    assert _messages_of(result) == {
        "current_password": "Enter your current password.",
        "new_password": "Enter a new password.",
    }


def returns_both_fields_in_one_answer_when_current_is_wrong_and_new_is_too_short() -> None:
    user = _patient()

    result = _change(user, "not-the-password", "short")

    assert sorted(_messages_of(result)) == ["current_password", "new_password"]
    assert SignInFailure.objects.count() == 1
