"""Section 7.1 steps 3 and 4: how long a hold and a code live and when a code stops working."""

import importlib
from datetime import UTC, datetime, timedelta
from types import ModuleType

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
ONE_SECOND = timedelta(seconds=1)


def _rules() -> ModuleType:
    """Imported per test, so a module not written yet fails its tests and not the collection."""
    return importlib.import_module("scheduling.domain.booking_codes")


def returns_ten_minutes_five_attempts_six_digits_when_constants_are_read() -> None:
    assert timedelta(minutes=10) == _rules().HOLD_LIFETIME
    assert timedelta(minutes=10) == _rules().CODE_LIFETIME
    assert _rules().MAXIMUM_ATTEMPTS == 5
    assert _rules().CODE_DIGITS == 6


def returns_false_when_attempts_used_is_5() -> None:
    assert _rules().code_is_usable(NOW + timedelta(minutes=5), 5, NOW) is False


def returns_true_when_attempts_used_is_4() -> None:
    assert _rules().code_is_usable(NOW + timedelta(minutes=5), 4, NOW) is True


def returns_false_when_code_expires_exactly_now() -> None:
    assert _rules().code_is_usable(NOW, 0, NOW) is False


def returns_true_one_second_before_expiry() -> None:
    assert _rules().code_is_usable(NOW + ONE_SECOND, 0, NOW) is True
