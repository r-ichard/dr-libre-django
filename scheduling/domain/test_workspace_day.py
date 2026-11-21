"""Section 9.1: the local day of a hospital, hour groups and the tiles of the day."""

from datetime import UTC, date, datetime

from scheduling.domain.vocabulary import AppointmentStatus

BERLIN = "Europe/Berlin"


def returns_bounds_of_local_day_when_zone_is_berlin() -> None:
    from scheduling.domain.workspace_day import local_day_bounds

    bounds = local_day_bounds(date(2030, 1, 7), BERLIN)

    assert bounds == (
        datetime(2030, 1, 6, 23, 0, tzinfo=UTC),
        datetime(2030, 1, 7, 23, 0, tzinfo=UTC),
    )


def returns_23_hour_day_when_clock_goes_forward() -> None:
    from scheduling.domain.workspace_day import local_day_bounds

    start, end = local_day_bounds(date(2030, 3, 31), BERLIN)

    assert end - start == datetime(2030, 1, 1, 23, tzinfo=UTC) - datetime(2030, 1, 1, tzinfo=UTC)


def returns_25_hour_day_when_clock_goes_back() -> None:
    from scheduling.domain.workspace_day import local_day_bounds

    start, end = local_day_bounds(date(2030, 10, 27), BERLIN)

    assert end - start == datetime(2030, 1, 2, 1, tzinfo=UTC) - datetime(2030, 1, 1, tzinfo=UTC)


def returns_by_local_hour_when_zone_is_not_utc() -> None:
    from scheduling.domain.workspace_day import group_by_local_hour

    late = datetime(2030, 1, 7, 23, 30, tzinfo=UTC)
    early = datetime(2030, 1, 7, 8, 15, tzinfo=UTC)
    same_hour = datetime(2030, 1, 7, 8, 45, tzinfo=UTC)

    groups = group_by_local_hour([early, same_hour, late], BERLIN)

    assert groups == {0: [late], 9: [early, same_hour]}


def returns_cancelled_apart_from_active_when_day_has_both() -> None:
    from scheduling.domain.workspace_day import day_tiles

    statuses = [
        AppointmentStatus.BOOKED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ]

    tiles = day_tiles(statuses)

    assert (tiles.active, tiles.cancelled, tiles.completed, tiles.no_show) == (3, 1, 1, 1)
