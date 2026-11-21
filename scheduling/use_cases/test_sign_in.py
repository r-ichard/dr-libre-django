"""Section 12.1: password sign-in. Equal answer, one hasher call on every path, lockout by
request clock, no readable address stored."""

import json
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth.hashers import MD5PasswordHasher, make_password

from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.request_context import RequestContext
from scheduling.domain.sign_in_rules import Home
from scheduling.models import AuditLogEntry, Session, User
from scheduling.models.access import SignInFailure
from scheduling.models.builders import make
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.sign_in import SignedIn, sign_in_with_password

pytestmark = pytest.mark.django_db

RIGHT_PHRASE = "correct horse battery staple"
WRONG_PHRASE = "wrong horse battery staple"
START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
LOCKOUT_LIMIT = 10
EMAIL = "jane.doe@example.test"
UNUSABLE_HASH = "!"


class CountingHasher(MD5PasswordHasher):
    algorithm = "counting_md5"
    calls = 0

    def encode(self, password: str, salt: str, iterations: int | None = None) -> str:
        CountingHasher.calls += 1
        return super().encode(password, salt).replace("md5$", "counting_md5$", 1)

    def verify(self, password: str, encoded: str) -> bool:
        CountingHasher.calls += 1
        return super().verify(password, encoded.replace("counting_md5$", "md5$", 1))


@pytest.fixture
def counting_hasher(settings: object) -> type[CountingHasher]:
    settings.PASSWORD_HASHERS = [  # type: ignore[attr-defined]
        "scheduling.use_cases.test_sign_in.CountingHasher",
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
    return CountingHasher


def _at(instant: datetime) -> AbstractContextManager[None]:
    return bind_request_context(RequestContext(correlation_id="corr-1", now=instant))


def _user(email: str = EMAIL, **overrides: object) -> User:
    fields = {"password": make_password(RIGHT_PHRASE), **overrides}
    user = make("User", email=email, **fields)
    assert isinstance(user, User)
    return user


def _attempt(password: str, at: datetime = START, email: str = EMAIL) -> Result[SignedIn]:
    with _at(at):
        return sign_in_with_password(email, password, "agent")


def _fail_times(count: int, email: str = EMAIL, at: datetime = START) -> None:
    for _ in range(count):
        _attempt(WRONG_PHRASE, at, email)


def returns_home_and_session_when_password_is_right() -> None:
    _user(role="PATIENT")

    result = _attempt(RIGHT_PHRASE)

    assert isinstance(result, Success)
    assert result.value.home == Home.PATIENT_PORTAL
    assert Session.objects.get().expires_at == START + timedelta(days=7)
    assert Session.objects.get().opened_by == "PASSWORD"


def returns_twelve_hour_session_when_admin_signs_in() -> None:
    _user(role="ADMIN")

    result = _attempt(RIGHT_PHRASE)

    assert isinstance(result, Success)
    assert result.value.home == Home.ADMIN_CONSOLE
    assert Session.objects.get().expires_at == START + timedelta(hours=12)


def returns_login_audit_with_actor_and_domain_only_when_password_is_right() -> None:
    user = _user()

    _attempt(RIGHT_PHRASE)

    entry = AuditLogEntry.objects.get(action="auth.login")
    assert entry.actor_id == user.pk
    assert entry.metadata["email_domain"] == "example.test"
    assert "jane" not in json.dumps(entry.metadata)


def returns_equal_unauthenticated_when_email_is_unknown_or_password_is_wrong() -> None:
    _user()

    unknown = _attempt(RIGHT_PHRASE, email="nobody@example.test")
    wrong = _attempt(WRONG_PHRASE)

    assert unknown == wrong == Failure.unauthenticated()
    assert Session.objects.count() == 0


def returns_one_hasher_call_when_email_is_unknown(counting_hasher: type[CountingHasher]) -> None:
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE, email="nobody@example.test")

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_password_is_wrong(counting_hasher: type[CountingHasher]) -> None:
    _user()
    counting_hasher.calls = 0

    _attempt(WRONG_PHRASE)

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_password_is_right(counting_hasher: type[CountingHasher]) -> None:
    _user()
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE)

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_user_is_inactive_with_usable_password(
    counting_hasher: type[CountingHasher],
) -> None:
    _user(is_active=False)
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE)

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_user_is_inactive_without_usable_password(
    counting_hasher: type[CountingHasher],
) -> None:
    _user(is_active=False, password=UNUSABLE_HASH, email_verified_at=START)
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE)

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_patient_has_no_password(
    counting_hasher: type[CountingHasher],
) -> None:
    _user(password=UNUSABLE_HASH, email_verified_at=START)
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE)

    assert counting_hasher.calls == 1


def returns_one_hasher_call_when_address_is_locked(
    counting_hasher: type[CountingHasher],
) -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT)
    counting_hasher.calls = 0

    _attempt(RIGHT_PHRASE)

    assert counting_hasher.calls == 1


def returns_unauthenticated_when_user_is_inactive_and_password_is_right() -> None:
    _user(is_active=False)

    assert _attempt(RIGHT_PHRASE) == Failure.unauthenticated()
    assert Session.objects.count() == 0


def returns_unauthenticated_when_tenth_failure_is_followed_by_correct_password() -> None:
    user = _user()
    _fail_times(LOCKOUT_LIMIT)

    result = _attempt(RIGHT_PHRASE, START + timedelta(minutes=1))

    assert result == Failure.unauthenticated()
    assert Session.objects.count() == 0
    lockout = AuditLogEntry.objects.get(action="auth.lockout")
    assert lockout.actor_id == user.pk
    assert lockout.metadata["email_domain"] == "example.test"


def returns_signed_in_when_clock_moves_fifteen_minutes_after_the_failures() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT)

    still_locked = _attempt(RIGHT_PHRASE, START + timedelta(minutes=14, seconds=59))
    after_window = _attempt(RIGHT_PHRASE, START + timedelta(minutes=15, seconds=1))

    assert still_locked == Failure.unauthenticated()
    assert after_window != Failure.unauthenticated()
    assert Session.objects.count() == 1


def returns_signed_in_when_ninth_failure_is_followed_by_correct_password() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT - 1)

    result = _attempt(RIGHT_PHRASE)

    assert result != Failure.unauthenticated()


def returns_zero_failures_when_sign_in_succeeds() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT - 1)
    _attempt(RIGHT_PHRASE)
    _fail_times(LOCKOUT_LIMIT - 1)

    result = _attempt(RIGHT_PHRASE)

    assert result != Failure.unauthenticated()


def returns_independent_counts_when_two_addresses_fail() -> None:
    _user()
    _user(email="other@example.test")
    _fail_times(LOCKOUT_LIMIT, email="other@example.test")

    result = _attempt(RIGHT_PHRASE)

    assert result != Failure.unauthenticated()


def returns_locked_when_unknown_address_fails_ten_times() -> None:
    _fail_times(LOCKOUT_LIMIT, email="nobody@example.test")

    _attempt(RIGHT_PHRASE, email="nobody@example.test")

    assert AuditLogEntry.objects.filter(action="auth.lockout", actor=None).count() == 1


def returns_no_readable_address_when_failure_is_recorded() -> None:
    _fail_times(1, email="Jane.Doe@Example.test")

    stored = SignInFailure.objects.get()
    assert "jane" not in json.dumps([stored.email_hash, str(stored.failed_at)]).lower()
    audit = AuditLogEntry.objects.get(action="auth.login_failed")
    assert "jane" not in json.dumps(audit.metadata).lower()
    assert audit.metadata["email_domain"] == "example.test"


def returns_same_count_when_address_differs_only_in_case() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT - 1, email="JANE.DOE@example.test")

    _attempt(WRONG_PHRASE)

    assert SignInFailure.objects.values("email_hash").distinct().count() == 1


def returns_audit_with_empty_actor_when_email_is_unknown() -> None:
    _attempt(RIGHT_PHRASE, email="nobody@example.test")

    entry = AuditLogEntry.objects.get(action="auth.login_failed")
    assert entry.actor_id is None
    assert entry.metadata["email_domain"] == "example.test"


def returns_failure_audit_with_actor_when_password_is_wrong() -> None:
    user = _user()

    _attempt(WRONG_PHRASE)

    assert AuditLogEntry.objects.get(action="auth.login_failed").actor_id == user.pk


def returns_signed_in_when_address_is_typed_in_other_case() -> None:
    _user()

    result = _attempt(RIGHT_PHRASE, email="Jane.DOE@Example.test")

    assert result != Failure.unauthenticated()


def returns_failure_count_in_lockout_audit_when_address_is_locked() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT)

    _attempt(RIGHT_PHRASE, START + timedelta(minutes=1))

    lockout = AuditLogEntry.objects.get(action="auth.lockout")
    assert lockout.metadata["counts"] == {"failure_count": LOCKOUT_LIMIT}


def returns_signed_in_when_failures_are_exactly_fifteen_minutes_old() -> None:
    _user()
    _fail_times(LOCKOUT_LIMIT)

    result = _attempt(RIGHT_PHRASE, START + timedelta(minutes=15))

    assert result != Failure.unauthenticated()


def returns_only_new_failure_stored_when_old_failures_left_the_window() -> None:
    _fail_times(3)

    _attempt(WRONG_PHRASE, START + timedelta(minutes=16))

    assert list(SignInFailure.objects.values_list("failed_at", flat=True)) == [
        START + timedelta(minutes=16)
    ]
