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


def returns_three_and_ten_when_link_limits_are_read() -> None:
    assert _rules().RATE_LIMITS[_rules().RateLimitScope.LINK] == _rules().RateLimit(
        per_email=3, per_address=10
    )


def returns_true_when_hits_equal_limit() -> None:
    assert _rules().is_limited(3, 3) is True


def returns_false_when_hits_are_one_below_limit() -> None:
    assert _rules().is_limited(2, 3) is False


def returns_window_start_one_hour_before_now() -> None:
    assert _rules().window_start(NOW) == NOW - timedelta(hours=1)


def returns_five_and_twenty_when_token_limits_are_read() -> None:
    assert _rules().RATE_LIMITS[_rules().RateLimitScope.TOKEN] == _rules().RateLimit(
        per_email=5, per_address=20
    )


def _hits_ago(*minutes: int) -> list[datetime]:
    return sorted(NOW - timedelta(minutes=amount) for amount in minutes)


def returns_3000_seconds_when_five_hits_fill_limit_five_and_oldest_is_ten_minutes_old() -> None:
    assert _rules().retry_after_seconds(_hits_ago(10, 8, 6, 4, 2), 5, NOW) == 3000


def returns_third_oldest_when_five_hits_exceed_limit_three() -> None:
    assert _rules().retry_after_seconds(_hits_ago(50, 40, 30, 20, 10), 3, NOW) == 1800


def returns_one_when_oldest_hit_leaves_this_very_second() -> None:
    assert _rules().retry_after_seconds(_hits_ago(60, 5), 2, NOW) == 1


def returns_rounded_up_when_oldest_hit_leaves_in_a_fraction_of_a_second() -> None:
    hits = [NOW - timedelta(hours=1) + timedelta(milliseconds=1500)]

    assert _rules().retry_after_seconds(hits, 1, NOW) == 2


def returns_3600_when_the_only_hit_is_now() -> None:
    assert _rules().retry_after_seconds([NOW], 1, NOW) == 3600


def returns_minutes_when_wait_is_twelve_minutes() -> None:
    assert _rules().wait_sentence(720) == "Try again in 12 minutes."


def returns_singular_when_wait_is_one_minute() -> None:
    assert _rules().wait_sentence(60) == "Try again in 1 minute."


def returns_seconds_when_wait_is_under_a_minute() -> None:
    assert _rules().wait_sentence(40) == "Try again in 40 seconds."


def returns_one_second_singular_when_wait_is_one_second() -> None:
    assert _rules().wait_sentence(1) == "Try again in 1 second."


def returns_rounded_up_minutes_when_wait_is_61_seconds() -> None:
    assert _rules().wait_sentence(61) == "Try again in 2 minutes."


def returns_1200_an_hour_for_schedule_and_600_for_fhir_per_address_and_no_email_limit() -> None:
    rules = _rules()

    assert rules.RATE_LIMITS[rules.RateLimitScope("schedule")] == rules.RateLimit(
        per_email=None, per_address=1200
    )
    assert rules.RATE_LIMITS[rules.RateLimitScope("fhir")] == rules.RateLimit(
        per_email=None, per_address=600
    )
