"""Task 23, spec 15.5: date search values with prefixes become half-open ranges."""

import os
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest

from scheduling.domain.fhir_dates import (
    bounded_window,
    bounds_of,
    combined_bounds,
    day_bounds,
    normalised_date,
)

DAY = timedelta(days=1)
JAN_7 = datetime(2030, 1, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2030-01-07", "eq2030-01-07"),
        ("ge2030-01-07T10:00:00Z", "ge2030-01-07T10:00:00Z"),
        ("lt2030-01-07T10:00", "lt2030-01-07T10:00:00Z"),
        ("le2030-01-07T10:00:00+01:00", "le2030-01-07T09:00:00Z"),
        ("2030-13-01", None),
        ("ne2030-01-07", None),
        ("soon", None),
    ],
)
def returns_normalised_value_or_none(text: str, expected: str | None) -> None:
    assert normalised_date(text) == expected


def returns_the_range_each_prefix_asks_for() -> None:
    assert bounds_of("eq2030-01-07") == (JAN_7, JAN_7 + DAY)
    assert bounds_of("ge2030-01-07") == (JAN_7, None)
    assert bounds_of("gt2030-01-07") == (JAN_7 + DAY, None)
    assert bounds_of("le2030-01-07") == (None, JAN_7 + DAY)
    assert bounds_of("lt2030-01-07") == (None, JAN_7)


def returns_first_and_last_day_when_range_is_combined() -> None:
    assert day_bounds(["ge2030-01-02", "lt2030-01-04"]) == (date(2030, 1, 2), date(2030, 1, 3))


def returns_none_when_window_is_open_empty_or_too_wide() -> None:
    week = timedelta(days=7)

    assert bounded_window(["ge2030-01-07"], week) is None
    assert bounded_window(["ge2030-01-07", "lt2030-01-07"], week) is None
    assert bounded_window(["ge2030-01-07", "lt2030-01-15"], week) is None
    assert bounded_window(["ge2030-01-07", "lt2030-01-14"], week) == (JAN_7, JAN_7 + week)


def returns_the_range_each_prefix_asks_for_when_the_value_is_an_instant() -> None:
    noon = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)
    one_second = timedelta(seconds=1)

    assert bounds_of("eq2030-01-07T12:00:00Z") == (noon, noon + one_second)
    assert bounds_of("gt2030-01-07T12:00:00Z") == (noon + one_second, None)
    assert bounds_of("le2030-01-07T12:00:00Z") == (None, noon + one_second)


def returns_only_the_high_bound_when_no_value_has_a_low_bound() -> None:
    assert combined_bounds(["lt2030-01-07"]) == (None, JAN_7)


def returns_an_open_end_or_start_when_the_range_is_open() -> None:
    assert day_bounds(["ge2030-01-07"]) == (date(2030, 1, 7), None)
    assert day_bounds(["le2030-01-07"]) == (None, date(2030, 1, 7))


@pytest.fixture
def tokyo_machine() -> Iterator[None]:
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Tokyo"
    time.tzset()
    yield
    if previous is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = previous
    time.tzset()


@pytest.mark.usefixtures("tokyo_machine")
def returns_utc_whatever_the_zone_of_the_machine_is() -> None:
    assert normalised_date("lt2030-01-07T10:00") == "lt2030-01-07T10:00:00Z"
    assert normalised_date("le2030-01-07T10:00:00+01:00") == "le2030-01-07T09:00:00Z"
