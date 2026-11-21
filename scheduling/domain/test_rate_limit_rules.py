"""Section 7.5: the hourly limits of hold and code requests, per email address and per network
address, over a rolling window."""

import importlib
from datetime import UTC, datetime, timedelta
from types import ModuleType

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


def _rules() -> ModuleType:
    """Imported per test, so a module not written yet fails its tests and not the collection."""
    return importlib.import_module("scheduling.domain.rate_limit_rules")


def returns_five_and_twenty_when_hold_limits_are_read() -> None:
    assert _rules().RATE_LIMITS[_rules().RateLimitScope.HOLD] == _rules().RateLimit(
        per_email=5, per_address=20
    )


def returns_three_and_ten_when_code_limits_are_read() -> None:
    assert _rules().RATE_LIMITS[_rules().RateLimitScope.CODE] == _rules().RateLimit(
        per_email=3, per_address=10
    )


def returns_true_when_hits_equal_limit() -> None:
    assert _rules().is_limited(3, 3) is True


def returns_false_when_hits_are_one_below_limit() -> None:
    assert _rules().is_limited(2, 3) is False


def returns_window_start_one_hour_before_now() -> None:
    assert _rules().window_start(NOW) == NOW - timedelta(hours=1)
