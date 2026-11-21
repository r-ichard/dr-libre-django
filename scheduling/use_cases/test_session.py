"""Section 12.2: open, resolve, extend and end a session; the request clock moves, nothing waits."""

import hashlib
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.failure import Failure
from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import AuditLogEntry, Session, User
from scheduling.models.builders import make
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session, resolve_session, sign_out

pytestmark = pytest.mark.django_db

OPENED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)


def _at(instant: datetime) -> AbstractContextManager[None]:
    return bind_request_context(RequestContext(correlation_id="corr-1", now=instant))


def _user(**overrides: object) -> User:
    user = make("User", **overrides)
    assert isinstance(user, User)
    return user


def _token_for(user: User, kind: SessionKind) -> str:
    with _at(OPENED_AT):
        return open_session(user, kind, "agent").token


def returns_user_agent_cut_to_three_hundred_characters_when_agent_is_longer() -> None:
    user = _user()

    with _at(OPENED_AT):
        open_session(user, SessionKind.PASSWORD, "x" * 301)

    assert Session.objects.get().user_agent == "x" * 300


@pytest.mark.parametrize("kind", [SessionKind.EMAIL_LINK, SessionKind.BOOKING_CODE])
def returns_session_expiring_in_twenty_four_hours_when_open_session_is_called_for_link_or_code(
    kind: SessionKind,
) -> None:
    user = _user(role="ADMIN")

    with _at(OPENED_AT):
        opened = open_session(user, kind, "agent")

    stored = Session.objects.get()
    assert stored.expires_at == OPENED_AT + timedelta(hours=24)
    assert stored.opened_by == kind
    assert stored.user_id == user.pk
    assert opened.session.pk == stored.pk


def returns_hash_of_token_when_session_is_stored() -> None:
    user = _user()

    token = _token_for(user, SessionKind.EMAIL_LINK)

    assert Session.objects.get().token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert len(token) >= 43


def returns_different_tokens_when_two_sessions_are_opened() -> None:
    user = _user()

    assert _token_for(user, SessionKind.EMAIL_LINK) != _token_for(user, SessionKind.EMAIL_LINK)


def returns_user_when_cookie_token_matches_a_live_session() -> None:
    user = _user()
    token = _token_for(user, SessionKind.EMAIL_LINK)

    with _at(OPENED_AT + timedelta(hours=1)):
        result = resolve_session(token)

    assert not isinstance(result, Failure)
    assert result.value.user.pk == user.pk


def returns_unauthenticated_when_token_is_unknown() -> None:
    with _at(OPENED_AT):
        result = resolve_session("not-a-token")

    assert result == Failure.unauthenticated()


def returns_unauthenticated_when_clock_passes_expiry() -> None:
    token = _token_for(_user(), SessionKind.EMAIL_LINK)
    expiry = OPENED_AT + timedelta(hours=24)

    with _at(expiry - ONE_SECOND):
        before = resolve_session(token)
    with _at(expiry):
        at_expiry = resolve_session(token)

    assert not isinstance(before, Failure)
    assert at_expiry == Failure.unauthenticated()


def returns_unauthenticated_when_user_is_deactivated() -> None:
    user = _user()
    token = _token_for(user, SessionKind.EMAIL_LINK)
    with _at(OPENED_AT + ONE_SECOND):
        assert not isinstance(resolve_session(token), Failure)
    user.is_active = False
    user.save()

    with _at(OPENED_AT + 2 * ONE_SECOND):
        result = resolve_session(token)

    assert result == Failure.unauthenticated()


def returns_longer_expiry_when_clock_moves_to_under_half_remaining() -> None:
    user = _user(role="PATIENT")
    with _at(OPENED_AT):
        token = open_session(user, SessionKind.PASSWORD, "").token
    later = OPENED_AT + timedelta(days=3, hours=12, seconds=1)

    with _at(later):
        result = resolve_session(token)

    assert not isinstance(result, Failure)
    assert Session.objects.get().expires_at == later + timedelta(days=7)
    assert result.value.extended is True


def returns_same_expiry_when_more_than_half_remains() -> None:
    user = _user(role="PATIENT")
    with _at(OPENED_AT):
        token = open_session(user, SessionKind.PASSWORD, "").token

    with _at(OPENED_AT + timedelta(days=1)):
        result = resolve_session(token)

    assert not isinstance(result, Failure)
    assert Session.objects.get().expires_at == OPENED_AT + timedelta(days=7)
    assert result.value.extended is False


def returns_same_expiry_when_link_session_is_resolved_late() -> None:
    token = _token_for(_user(), SessionKind.EMAIL_LINK)

    with _at(OPENED_AT + timedelta(hours=23)):
        resolve_session(token)

    assert Session.objects.get().expires_at == OPENED_AT + timedelta(hours=24)


def returns_unauthenticated_when_session_is_signed_out_and_token_reused() -> None:
    user = _user()
    token = _token_for(user, SessionKind.EMAIL_LINK)

    with _at(OPENED_AT + ONE_SECOND):
        sign_out(token)
        result = resolve_session(token)

    assert result == Failure.unauthenticated()
    assert Session.objects.count() == 0


def returns_logout_audit_with_actor_when_session_is_signed_out() -> None:
    user = _user()
    token = _token_for(user, SessionKind.EMAIL_LINK)

    with _at(OPENED_AT + ONE_SECOND):
        sign_out(token)

    entry = AuditLogEntry.objects.get(action="auth.logout")
    assert entry.actor_id == user.pk
    assert entry.entity_type == "Session"


def returns_nothing_changed_when_sign_out_token_is_unknown() -> None:
    with _at(OPENED_AT):
        sign_out("not-a-token")

    assert AuditLogEntry.objects.filter(action="auth.logout").count() == 0
