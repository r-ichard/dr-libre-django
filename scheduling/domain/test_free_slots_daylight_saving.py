"""Section 4 and 5.1: weekly availability is local wall-clock time across clock changes.

A start whose wall-clock time does not exist is skipped; one that exists twice is offered
once, at its first occurrence. Northern (Paris) and southern (Sydney) changes.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain.free_slots import AvailabilityWindow, SlotType, TimeRange, free_slots

HALF_HOUR = SlotType(duration=timedelta(minutes=30), buffer=timedelta(0))
LONG_BEFORE = datetime(2020, 1, 1, tzinfo=UTC)


def _night_rule() -> AvailabilityWindow:
    return AvailabilityWindow(
        0, time(1, 30), time(4, 0), timedelta(minutes=30), date(2020, 1, 1), None
    )


def _whole_day_slots(zone_name: str, day: date, rule: AvailabilityWindow) -> list[datetime]:
    zone = ZoneInfo(zone_name)
    start = datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(UTC)
    window = TimeRange(start - timedelta(hours=2), start + timedelta(hours=40))
    inside = free_slots([rule], HALF_HOUR, [], [], window, LONG_BEFORE, zone)
    return [slot for slot in inside if slot.astimezone(zone).date() == day]


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("zone_name", "day", "expected"),
    [
        (
            "Europe/Paris",
            date(2027, 3, 28),
            [_utc(2027, 3, 28, 0, 30), _utc(2027, 3, 28, 1, 0), _utc(2027, 3, 28, 1, 30)],
        ),
        (
            "Australia/Sydney",
            date(2026, 10, 4),
            [_utc(2026, 10, 3, 15, 30), _utc(2026, 10, 3, 16, 0), _utc(2026, 10, 3, 16, 30)],
        ),
    ],
)
def returns_no_slot_for_local_starts_that_do_not_exist_when_clocks_spring_forward(
    zone_name: str, day: date, expected: list[datetime]
) -> None:
    assert _whole_day_slots(zone_name, day, _night_rule()) == expected


@pytest.mark.parametrize(
    ("zone_name", "day", "expected"),
    [
        (
            "Europe/Paris",
            date(2026, 10, 25),
            [
                _utc(2026, 10, 24, 23, 30),
                _utc(2026, 10, 25, 0, 0),
                _utc(2026, 10, 25, 0, 30),
                _utc(2026, 10, 25, 2, 0),
                _utc(2026, 10, 25, 2, 30),
            ],
        ),
        (
            "Australia/Sydney",
            date(2027, 4, 4),
            [
                _utc(2027, 4, 3, 14, 30),
                _utc(2027, 4, 3, 15, 0),
                _utc(2027, 4, 3, 15, 30),
                _utc(2027, 4, 3, 17, 0),
                _utc(2027, 4, 3, 17, 30),
            ],
        ),
    ],
)
def returns_ambiguous_local_start_once_at_first_occurrence_when_clocks_fall_back(
    zone_name: str, day: date, expected: list[datetime]
) -> None:
    assert _whole_day_slots(zone_name, day, _night_rule()) == expected


@pytest.mark.parametrize(
    ("zone_name", "first_day", "second_day", "expected"),
    [
        (
            "Europe/Paris",
            date(2027, 3, 27),
            date(2027, 3, 28),
            [_utc(2027, 3, 27, 8), _utc(2027, 3, 28, 7)],
        ),
        (
            "Australia/Sydney",
            date(2026, 10, 3),
            date(2026, 10, 4),
            [_utc(2026, 10, 2, 23), _utc(2026, 10, 3, 22)],
        ),
    ],
)
def returns_same_local_time_with_other_utc_offset_on_each_side_of_a_change(
    zone_name: str, first_day: date, second_day: date, expected: list[datetime]
) -> None:
    zone = ZoneInfo(zone_name)
    every_day = [
        AvailabilityWindow(
            weekday, time(9, 0), time(9, 30), timedelta(minutes=30), date(2020, 1, 1), None
        )
        for weekday in range(7)
    ]
    window = TimeRange(
        datetime.combine(first_day, time(0, 0), tzinfo=zone),
        datetime.combine(second_day, time(23, 59), tzinfo=zone),
    )
    assert free_slots(every_day, HALF_HOUR, [], [], window, LONG_BEFORE, zone) == expected


def returns_nothing_when_the_whole_rule_lies_in_the_skipped_hour() -> None:
    gap_rule = AvailabilityWindow(
        0, time(2, 0), time(3, 0), timedelta(minutes=15), date(2020, 1, 1), None
    )
    assert _whole_day_slots("Europe/Paris", date(2027, 3, 28), gap_rule) == []
