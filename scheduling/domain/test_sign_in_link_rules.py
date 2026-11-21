"""Section 7.3: a sign-in link works for 15 minutes and once, unless it was cancelled."""

import importlib
from datetime import UTC, datetime, timedelta
from types import ModuleType

ISSUED_AT = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)
EXPIRES_AT = ISSUED_AT + timedelta(minutes=15)


def _rules() -> ModuleType:
    """Imported per test, so a module not written yet fails its tests and not the collection."""
    return importlib.import_module("scheduling.domain.sign_in_link_rules")


def _usable(**overrides: object) -> bool:
    state: dict[str, object] = {
        "now": ISSUED_AT + timedelta(minutes=5),
        "expires_at": EXPIRES_AT,
        "used_at": None,
        "cancelled_at": None,
    }
    return bool(_rules().link_is_usable(**{**state, **overrides}))


def returns_fifteen_minutes_when_link_lifetime_is_read() -> None:
    assert timedelta(minutes=15) == _rules().LINK_LIFETIME


def returns_at_least_sixteen_bytes_when_token_size_is_read() -> None:
    assert _rules().TOKEN_BYTES >= 16


def returns_true_when_link_is_unused_uncancelled_and_before_expiry() -> None:
    assert _usable() is True


def returns_true_one_second_before_expiry() -> None:
    assert _usable(now=EXPIRES_AT - ONE_SECOND) is True


def returns_false_at_exactly_fifteen_minutes() -> None:
    assert _usable(now=EXPIRES_AT) is False


def returns_false_when_link_was_used() -> None:
    assert _usable(used_at=ISSUED_AT + ONE_SECOND) is False


def returns_false_when_link_was_cancelled() -> None:
    assert _usable(cancelled_at=ISSUED_AT + ONE_SECOND) is False
