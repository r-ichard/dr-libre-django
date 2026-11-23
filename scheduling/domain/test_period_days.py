"""Section 4: a period cut into the part that falls in each local day."""

from datetime import UTC, date, datetime

BERLIN = "Europe/Berlin"


def _days(first: date, count: int) -> list[date]:
    return [date.fromordinal(first.toordinal() + offset) for offset in range(count)]


def returns_whole_day_part_when_period_covers_the_day() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)
    ends_at = datetime(2026, 12, 4, 0, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, _days(date(2026, 12, 1), 4), BERLIN)

    wednesday = parts[1]
    assert wednesday.day == date(2026, 12, 2)
    assert wednesday.whole_day is True
    assert wednesday.starts_at == datetime(2026, 12, 1, 23, 0, tzinfo=UTC)
    assert wednesday.ends_at == datetime(2026, 12, 2, 23, 0, tzinfo=UTC)


def returns_partial_first_and_last_parts_when_period_starts_and_ends_inside_days() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)
    ends_at = datetime(2026, 12, 4, 0, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, _days(date(2026, 12, 1), 4), BERLIN)

    first, last = parts[0], parts[-1]
    assert (first.day, first.starts_at, first.ends_at, first.whole_day) == (
        date(2026, 12, 1),
        starts_at,
        datetime(2026, 12, 1, 23, 0, tzinfo=UTC),
        False,
    )
    assert (last.day, last.starts_at, last.ends_at, last.whole_day) == (
        date(2026, 12, 4),
        datetime(2026, 12, 3, 23, 0, tzinfo=UTC),
        ends_at,
        False,
    )


def returns_only_listed_days_when_period_is_longer_than_the_window() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)
    ends_at = datetime(2026, 12, 20, 0, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, _days(date(2026, 12, 7), 2), BERLIN)

    assert [part.day for part in parts] == [date(2026, 12, 7), date(2026, 12, 8)]


def returns_twenty_five_hour_part_when_clocks_go_back() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
    ends_at = datetime(2026, 11, 20, 0, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, [date(2026, 10, 25)], BERLIN)

    assert len(parts) == 1
    assert parts[0].whole_day is True
    assert parts[0].starts_at == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    assert parts[0].ends_at == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)


def returns_twenty_three_hour_part_when_clocks_go_forward() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 3, 20, 0, 0, tzinfo=UTC)
    ends_at = datetime(2026, 4, 20, 0, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, [date(2026, 3, 29)], BERLIN)

    assert parts[0].starts_at == datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
    assert parts[0].ends_at == datetime(2026, 3, 29, 22, 0, tzinfo=UTC)
    assert parts[0].whole_day is True


def returns_no_part_when_period_ends_exactly_at_local_midnight() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 12, 1, 8, 0, tzinfo=UTC)
    ends_at = datetime(2026, 12, 1, 23, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, _days(date(2026, 12, 1), 2), BERLIN)

    assert [part.day for part in parts] == [date(2026, 12, 2)] or parts == [
        part for part in parts if part.day == date(2026, 12, 1)
    ]
    assert all(part.day != date(2026, 12, 2) for part in parts)


def returns_no_part_when_period_starts_exactly_at_local_midnight_after_the_day() -> None:
    from scheduling.domain.period_days import cut_into_days

    starts_at = datetime(2026, 12, 1, 23, 0, tzinfo=UTC)
    ends_at = datetime(2026, 12, 2, 8, 0, tzinfo=UTC)

    parts = cut_into_days(starts_at, ends_at, [date(2026, 12, 1)], BERLIN)

    assert parts == []
