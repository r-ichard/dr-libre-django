"""Section 6.2: which type the times are for and the first starts, in 31 day chunks."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import AvailabilityWindow, SlotType, TimeRange
from scheduling.domain.search_availability import BookableType, next_starts, shortest_type
from scheduling.domain.slot_search import ClinicianSchedule

UTC_ZONE = ZoneInfo("UTC")
NOW = datetime(2030, 1, 7, 0, 0, tzinfo=UTC)
HALF_HOUR = SlotType(duration=timedelta(minutes=30), buffer=timedelta(0))


def _types(*rows: tuple[int, str, int]) -> list[BookableType]:
    return [BookableType(UUID(int=number), name, minutes) for minutes, name, number in rows]


def _weekly(weekday: int, valid_from: date) -> ClinicianSchedule:
    window = AvailabilityWindow(
        weekday, time(9, 0), time(9, 30), timedelta(minutes=30), valid_from, None
    )
    return ClinicianSchedule([window], [], [])


def returns_the_shortest_type() -> None:
    types = _types((60, "Long", 1), (20, "Short", 2), (45, "Middle", 3))

    assert shortest_type(types).name == "Short"


def returns_the_name_first_when_durations_tie() -> None:
    types = _types((30, "Zeta", 1), (30, "Alpha", 2))

    assert shortest_type(types).name == "Alpha"


def returns_the_lower_id_when_duration_and_name_tie() -> None:
    types = _types((30, "Same", 9), (30, "Same", 4))

    assert shortest_type(types).id == UUID(int=4)


def returns_the_first_three_starts_across_the_31_day_border() -> None:
    early = AvailabilityWindow(
        1, time(9, 0), time(9, 30), timedelta(minutes=30), date(2030, 1, 1), date(2030, 1, 8)
    )
    late = AvailabilityWindow(
        1, time(9, 0), time(9, 30), timedelta(minutes=30), date(2030, 2, 11), None
    )
    window = TimeRange(NOW, NOW + timedelta(days=90))

    starts = next_starts(
        ClinicianSchedule([early, late], [], []), HALF_HOUR, window, NOW, UTC_ZONE, 3
    )

    assert starts == [
        datetime(2030, 1, 7, 9, 0, tzinfo=UTC),
        datetime(2030, 2, 11, 9, 0, tzinfo=UTC),
        datetime(2030, 2, 18, 9, 0, tzinfo=UTC),
    ]


def returns_a_start_from_the_second_chunk_when_nothing_is_free_before() -> None:
    schedule = _weekly(weekday=1, valid_from=date(2030, 3, 1))
    window = TimeRange(NOW, NOW + timedelta(days=90))

    starts = next_starts(schedule, HALF_HOUR, window, NOW, UTC_ZONE, 1)

    assert starts == [datetime(2030, 3, 4, 9, 0, tzinfo=UTC)]


def returns_starts_from_the_third_chunk_when_only_the_last_days_are_free() -> None:
    schedule = _weekly(weekday=1, valid_from=date(2030, 4, 1))
    window = TimeRange(NOW, NOW + timedelta(days=90))

    starts = next_starts(schedule, HALF_HOUR, window, NOW, UTC_ZONE, 3)

    assert starts == [datetime(2030, 4, 1, 9, 0, tzinfo=UTC)]


def returns_fewer_starts_when_fewer_exist() -> None:
    schedule = ClinicianSchedule(
        [
            AvailabilityWindow(
                1,
                time(9, 0),
                time(9, 30),
                timedelta(minutes=30),
                date(2030, 1, 1),
                date(2030, 1, 14),
            )
        ],
        [],
        [],
    )
    window = TimeRange(NOW, NOW + timedelta(days=90))

    starts = next_starts(schedule, HALF_HOUR, window, NOW, UTC_ZONE, 3)

    assert len(starts) == 2


def returns_nothing_when_the_clinician_has_no_rule() -> None:
    window = TimeRange(NOW, NOW + timedelta(days=90))

    assert next_starts(ClinicianSchedule([], [], []), HALF_HOUR, window, NOW, UTC_ZONE, 3) == []


def returns_no_start_after_the_end_of_the_window() -> None:
    schedule = _weekly(weekday=1, valid_from=date(2030, 1, 1))
    window = TimeRange(NOW, NOW + timedelta(days=7))

    starts = next_starts(schedule, HALF_HOUR, window, NOW, UTC_ZONE, 3)

    assert starts == [datetime(2030, 1, 7, 9, 0, tzinfo=UTC)]


def returns_the_start_across_the_border_when_the_slot_ends_after_the_first_chunk() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    thursday_after_midnight = AvailabilityWindow(
        4, time(0, 45), time(1, 15), timedelta(minutes=30), date(2030, 2, 1), None
    )
    window = TimeRange(NOW, NOW + timedelta(days=90))

    starts = next_starts(
        ClinicianSchedule([thursday_after_midnight], [], []), HALF_HOUR, window, NOW, berlin, 1
    )

    assert starts == [datetime(2030, 2, 6, 23, 45, tzinfo=UTC)]


def returns_local_wall_clock_starts_when_the_zone_is_not_utc() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    window = TimeRange(NOW, NOW + timedelta(days=7))

    starts = next_starts(_weekly(1, date(2030, 1, 1)), HALF_HOUR, window, NOW, berlin, 1)

    assert starts == [datetime(2030, 1, 7, 8, 0, tzinfo=UTC)]


def returns_only_starts_the_filter_keeps_and_drops_the_rest() -> None:
    schedule = _weekly(weekday=1, valid_from=date(2030, 1, 1))
    window = TimeRange(NOW, NOW + timedelta(days=40))
    skipped = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)

    starts = next_starts(
        schedule, HALF_HOUR, window, NOW, UTC_ZONE, 2, keep=lambda start: start != skipped
    )

    assert starts == [
        datetime(2030, 1, 14, 9, 0, tzinfo=UTC),
        datetime(2030, 1, 21, 9, 0, tzinfo=UTC),
    ]


def returns_without_asking_the_filter_about_later_chunks_when_enough_starts_are_found() -> None:
    asked: list[datetime] = []

    def keep(start: datetime) -> bool:
        asked.append(start)
        return True

    window = TimeRange(NOW, NOW + timedelta(days=90))
    next_starts(_weekly(1, date(2030, 1, 1)), HALF_HOUR, window, NOW, UTC_ZONE, 5, keep=keep)

    assert max(asked) < NOW + timedelta(days=31)
