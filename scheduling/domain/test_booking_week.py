from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo("Australia/Sydney")
BERLIN = ZoneInfo("Europe/Berlin")


def returns_monday_to_sunday_in_utc_when_week_is_asked_for_a_date_in_sydney() -> None:
    from scheduling.domain.booking_week import week_range

    window = week_range(date(2030, 1, 9), SYDNEY)

    assert window.starts_at == datetime(2030, 1, 6, 13, 0, tzinfo=UTC)
    assert window.ends_at == datetime(2030, 1, 13, 13, 0, tzinfo=UTC)


def returns_a_seven_day_range_one_hour_longer_when_a_clock_change_ends_inside_the_week() -> None:
    from scheduling.domain.booking_week import week_range

    window = week_range(date(2030, 10, 23), BERLIN)

    assert window.starts_at == datetime(2030, 10, 20, 22, 0, tzinfo=UTC)
    assert window.ends_at == datetime(2030, 10, 27, 23, 0, tzinfo=UTC)


def returns_previous_and_next_monday_when_week_is_computed() -> None:
    from scheduling.domain.booking_week import next_week_start, previous_week_start

    assert previous_week_start(date(2030, 1, 9)) == date(2029, 12, 31)
    assert next_week_start(date(2030, 1, 9)) == date(2030, 1, 14)


def returns_slots_grouped_under_their_local_day_when_utc_dates_differ() -> None:
    from scheduling.domain.booking_week import group_by_local_day

    late = datetime(2030, 1, 7, 23, 30, tzinfo=UTC)
    early = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)

    days = group_by_local_day([late, early], SYDNEY)

    assert days == {date(2030, 1, 7): [early], date(2030, 1, 8): [late]}
