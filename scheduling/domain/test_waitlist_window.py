"""Task 15: the waitlist form speaks days, the use case speaks instants."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.waitlist_window import window_instants

PARIS = ZoneInfo("Europe/Paris")


def returns_start_of_first_day_and_start_of_day_after_last_in_hospital_zone() -> None:
    result = window_instants(date(2030, 1, 7), date(2030, 1, 8), PARIS)

    assert result == Success(
        (datetime(2030, 1, 6, 23, 0, tzinfo=UTC), datetime(2030, 1, 8, 23, 0, tzinfo=UTC))
    )


def returns_end_after_a_twenty_three_hour_day_when_last_day_is_the_spring_clock_change() -> None:
    result = window_instants(date(2030, 3, 31), date(2030, 3, 31), PARIS)

    assert result == Success(
        (datetime(2030, 3, 30, 23, 0, tzinfo=UTC), datetime(2030, 3, 31, 22, 0, tzinfo=UTC))
    )


def returns_one_day_window_when_first_and_last_day_are_the_same() -> None:
    result = window_instants(date(2030, 1, 7), date(2030, 1, 7), PARIS)

    assert result == Success(
        (datetime(2030, 1, 6, 23, 0, tzinfo=UTC), datetime(2030, 1, 7, 23, 0, tzinfo=UTC))
    )


def returns_invalid_input_when_last_day_is_before_first_day() -> None:
    result = window_instants(date(2030, 1, 8), date(2030, 1, 7), PARIS)

    assert result == Failure.invalid_input(
        [FieldMessage("latest_day", "The last day cannot be before the first day.")]
    )


def returns_instants_in_utc_zone() -> None:
    result = window_instants(date(2030, 1, 7), date(2030, 1, 7), PARIS)

    assert isinstance(result, Success)
    assert all(instant.tzinfo is UTC for instant in result.value)
