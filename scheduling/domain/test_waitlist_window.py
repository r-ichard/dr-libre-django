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


def _words(earliest: datetime, latest: datetime, zone: str) -> str:
    from scheduling.domain.waitlist_window import window_words

    return window_words(earliest, latest, ZoneInfo(zone))


def returns_one_day_when_window_is_one_day() -> None:
    earliest = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 26, 23, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == "Thursday 26 November 2026 (Europe/Berlin)"


def returns_last_day_two_days_on_when_window_is_two_days() -> None:
    earliest = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 27, 23, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == (
        "from Thursday 26 November 2026 to Friday 27 November 2026 (Europe/Berlin)"
    )


def returns_30_november_when_window_ends_on_last_day_of_month() -> None:
    earliest = datetime(2026, 11, 29, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == ("Monday 30 November 2026 (Europe/Berlin)")


def returns_chosen_days_when_hospital_is_east_of_utc() -> None:
    earliest = datetime(2026, 11, 25, 11, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 27, 11, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Pacific/Auckland") == (
        "from Thursday 26 November 2026 to Friday 27 November 2026 (Pacific/Auckland)"
    )


def returns_chosen_days_when_hospital_is_west_of_utc() -> None:
    earliest = datetime(2026, 11, 26, 8, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 28, 8, 0, tzinfo=UTC)

    assert _words(earliest, latest, "America/Los_Angeles") == (
        "from Thursday 26 November 2026 to Friday 27 November 2026 (America/Los_Angeles)"
    )


def returns_day_of_end_when_end_is_not_midnight() -> None:
    earliest = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 27, 16, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == (
        "from Thursday 26 November 2026 to Friday 27 November 2026 (Europe/Berlin)"
    )


def returns_the_first_day_alone_when_the_window_has_no_length() -> None:
    instant = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)

    assert _words(instant, instant, "Europe/Berlin") == "Thursday 26 November 2026 (Europe/Berlin)"


def returns_day_number_without_leading_zero_when_day_is_below_ten() -> None:
    earliest = datetime(2026, 12, 4, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 12, 5, 23, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == "Saturday 5 December 2026 (Europe/Berlin)"


def returns_from_and_to_words_when_window_covers_several_days() -> None:
    earliest = datetime(2026, 11, 22, 23, 0, tzinfo=UTC)
    latest = datetime(2026, 11, 29, 23, 0, tzinfo=UTC)

    assert _words(earliest, latest, "Europe/Berlin") == (
        "from Monday 23 November 2026 to Sunday 29 November 2026 (Europe/Berlin)"
    )
