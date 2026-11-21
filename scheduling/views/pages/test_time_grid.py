"""Task 17: the shared time grid puts items on the 07:00 to 19:00 axis and keeps the rest apart."""

from datetime import UTC, datetime, timedelta

from scheduling.views.pages.time_grid import GridItem, axis_rows, grid_column

ZONE = "UTC"
WINDOW_START = datetime(2030, 1, 7, 0, 0, tzinfo=UTC)
WINDOW = (WINDOW_START, WINDOW_START + timedelta(days=1))


def _item(starts_at: datetime, minutes: int = 30) -> GridItem:
    return GridItem(starts_at, starts_at + timedelta(minutes=minutes), ("line",), "", "", None)


def returns_hour_labels_on_even_rows_and_blank_on_half_hours() -> None:
    axis = axis_rows()

    assert len(axis) == 24
    assert axis[0] == "07:00" and axis[2] == "08:00" and axis[22] == "18:00"
    assert all(label == "" for label in axis[1::2])


def returns_no_item_when_it_ends_exactly_when_the_window_starts() -> None:
    before = _item(WINDOW_START - timedelta(minutes=30))

    column = grid_column("Day", "Day", [before], WINDOW, ZONE)

    assert column["inside"] == [] and column["outside"] == []


def returns_no_item_when_it_starts_exactly_when_the_window_ends() -> None:
    after = _item(WINDOW[1])

    column = grid_column("Day", "Day", [after], WINDOW, ZONE)

    assert column["inside"] == [] and column["outside"] == []


def returns_item_inside_when_on_grid_and_outside_when_before_seven() -> None:
    on_grid = _item(WINDOW_START + timedelta(hours=9))
    early = _item(WINDOW_START + timedelta(hours=6))

    column = grid_column("Day", "Day", [on_grid, early], WINDOW, ZONE)

    inside, outside = column["inside"], column["outside"]
    assert isinstance(inside, list) and isinstance(outside, list)
    assert len(inside) == 1 and len(outside) == 1
