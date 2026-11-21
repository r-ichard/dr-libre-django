"""Section 5.1: a slot lasts real elapsed time and must end within the rule's wall-clock end.

Both hemispheres: New York changes in March and November, Sydney in October and April.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain.free_slots import AvailabilityWindow, SlotType, TimeRange, free_slots

LONG_BEFORE = datetime(2020, 1, 1, tzinfo=UTC)
HALF_HOUR_STEP = timedelta(minutes=30)


def _slots(
    zone_name: str, day: date, start: time, end: time, duration_minutes: int
) -> list[datetime]:
    zone = ZoneInfo(zone_name)
    rule = AvailabilityWindow(0, start, end, HALF_HOUR_STEP, date(2020, 1, 1), None)
    midnight = datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(UTC)
    window = TimeRange(midnight - timedelta(hours=2), midnight + timedelta(hours=40))
    slot_type = SlotType(duration=timedelta(minutes=duration_minutes), buffer=timedelta(0))
    offered = free_slots([rule], slot_type, [], [], window, LONG_BEFORE, zone)
    return [slot for slot in offered if slot.astimezone(zone).date() == day]


def _utc(month: int, day: int, hour: int, minute: int = 0, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("zone_name", "day"),
    [("America/New_York", date(2026, 3, 8)), ("Australia/Sydney", date(2026, 10, 4))],
)
def returns_no_slot_when_spring_forward_real_end_passes_rule_end(zone_name: str, day: date) -> None:
    # 01:00 and 01:30 hour-long slots end at 03:00 and 03:30 on the wall clock, after 02:30.
    assert _slots(zone_name, day, time(1, 0), time(2, 30), 60) == []


@pytest.mark.parametrize(
    ("zone_name", "day", "expected"),
    [
        (
            "America/New_York",
            date(2026, 11, 1),
            [_utc(11, 1, 4, 0), _utc(11, 1, 4, 30), _utc(11, 1, 5, 0), _utc(11, 1, 5, 30)],
        ),
        (
            "Australia/Sydney",
            date(2026, 4, 5),
            [_utc(4, 4, 14, 0), _utc(4, 4, 14, 30), _utc(4, 4, 15, 0), _utc(4, 4, 15, 30)],
        ),
    ],
)
def returns_slot_when_fall_back_real_end_is_within_rule_end(
    zone_name: str, day: date, expected: list[datetime]
) -> None:
    # 90 minute slots; the last first-occurrence start ends exactly at the rule's wall-clock end.
    rule_start, rule_end = (
        (time(0, 0), time(2, 0)) if "York" in zone_name else (time(1, 0), time(3, 0))
    )
    assert _slots(zone_name, day, rule_start, rule_end, 90) == expected
