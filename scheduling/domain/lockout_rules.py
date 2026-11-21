"""Section 12.1: ten failures within fifteen minutes lock an address."""

from datetime import datetime, timedelta

LOCKOUT_FAILURES = 10
LOCKOUT_WINDOW = timedelta(minutes=15)


def window_start(now: datetime) -> datetime:
    return now - LOCKOUT_WINDOW


def is_locked(failure_count: int) -> bool:
    return failure_count >= LOCKOUT_FAILURES
