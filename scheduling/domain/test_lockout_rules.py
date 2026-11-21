"""Section 12.1: ten failures in fifteen minutes lock an address."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.lockout_rules import is_locked, window_start

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def returns_locked_when_ten_failures_counted() -> None:
    assert is_locked(10) is True


def returns_open_when_nine_failures_counted() -> None:
    assert is_locked(9) is False


def returns_window_start_fifteen_minutes_before_now() -> None:
    assert window_start(NOW) == NOW - timedelta(minutes=15)
