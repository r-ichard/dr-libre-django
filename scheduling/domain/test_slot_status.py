"""Task 23, spec 15.5: why a start is busy, and which reason wins."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.free_slots import BusyInterval
from scheduling.domain.slot_status import busy_status

START = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
HALF_HOUR = timedelta(minutes=30)
NOTHING: list[BusyInterval] = []
OVER_START = [BusyInterval(START, START + HALF_HOUR)]


def returns_none_when_nothing_blocks() -> None:
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, NOTHING, NOTHING) is None


def returns_each_status_for_its_own_reason() -> None:
    assert busy_status(START, HALF_HOUR, timedelta(0), OVER_START, NOTHING, NOTHING) == (
        "busy-unavailable"
    )
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, OVER_START, NOTHING) == "busy"
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, NOTHING, OVER_START) == (
        "busy-tentative"
    )


def returns_time_off_before_appointment_before_hold_when_all_overlap() -> None:
    assert busy_status(START, HALF_HOUR, timedelta(0), OVER_START, OVER_START, OVER_START) == (
        "busy-unavailable"
    )
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, OVER_START, OVER_START) == "busy"


def returns_busy_when_the_buffer_of_an_earlier_appointment_reaches_the_start() -> None:
    earlier = [BusyInterval(START - HALF_HOUR, START)]

    assert busy_status(START, HALF_HOUR, timedelta(minutes=5), NOTHING, earlier, NOTHING) == "busy"
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, earlier, NOTHING) is None
    assert busy_status(START, HALF_HOUR, timedelta(0), earlier, NOTHING, NOTHING) is None


def returns_none_when_a_block_starts_exactly_where_the_slot_ends() -> None:
    later = [BusyInterval(START + HALF_HOUR, START + 2 * HALF_HOUR)]

    assert busy_status(START, HALF_HOUR, timedelta(0), later, NOTHING, NOTHING) is None
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, later, NOTHING) is None
    assert busy_status(START, HALF_HOUR, timedelta(0), NOTHING, NOTHING, later) is None
