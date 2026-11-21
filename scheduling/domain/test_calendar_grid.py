"""Section 9.2: a time span to rows of the 07:00 to 19:00 grid of 30 minute rows (24 rows)."""

from datetime import UTC, datetime, timedelta

BERLIN = "Europe/Berlin"


def _berlin(hour: int, minute: int) -> datetime:
    """January: Berlin is one hour ahead of UTC."""
    return datetime(2030, 1, 7, hour - 1, minute, tzinfo=UTC)


def returns_block_at_row_6_span_3_when_starts_0930_ends_1100() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(9, 30), _berlin(11, 0), BERLIN) == GridPlacement(
        first_row=6, span=3
    )


def returns_block_at_row_1_when_starts_at_grid_start() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(7, 0), _berlin(7, 30), BERLIN) == GridPlacement(
        first_row=1, span=1
    )


def returns_nothing_when_starts_0630() -> None:
    from scheduling.domain.calendar_grid import place_in_grid

    assert place_in_grid(_berlin(6, 30), _berlin(7, 30), BERLIN) is None


def returns_nothing_when_starts_at_grid_end() -> None:
    from scheduling.domain.calendar_grid import place_in_grid

    assert place_in_grid(_berlin(19, 0), _berlin(19, 30), BERLIN) is None


def returns_span_when_ends_after_1900() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(18, 30), _berlin(19, 30), BERLIN) == GridPlacement(
        first_row=24, span=1
    )


def returns_span_up_when_ends_between_rows() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(9, 0), _berlin(9, 45), BERLIN) == GridPlacement(
        first_row=5, span=2
    )


def returns_row_21_when_starts_1725() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(17, 25), _berlin(17, 55), BERLIN) == GridPlacement(
        first_row=21, span=1
    )


def returns_last_row_when_starts_1850() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(18, 50), _berlin(19, 20), BERLIN) == GridPlacement(
        first_row=24, span=1
    )


def returns_whole_row_number_when_start_is_inside_a_row() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    assert place_in_grid(_berlin(9, 45), _berlin(10, 15), BERLIN) == GridPlacement(
        first_row=6, span=1
    )


def returns_extra_row_when_span_is_one_second_over_a_row() -> None:
    from scheduling.domain.calendar_grid import GridPlacement, place_in_grid

    ends_at = _berlin(10, 0) + timedelta(seconds=1)

    assert place_in_grid(_berlin(9, 30), ends_at, BERLIN) == GridPlacement(first_row=6, span=2)


def returns_labels_every_hour_from_0700_to_1900() -> None:
    from scheduling.domain.calendar_grid import HOUR_LABELS

    assert HOUR_LABELS[0] == "07:00"
    assert HOUR_LABELS[-1] == "19:00"
    assert len(HOUR_LABELS) == 13
