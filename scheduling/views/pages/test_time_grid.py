"""Section 9: the time grid places items on the 07:00 to 19:00 axis; the rest stay apart."""

from datetime import UTC, datetime, timedelta

from scheduling.views.pages.time_grid import GridItem, axis_rows, grid_column

ZONE = "UTC"
WINDOW_START = datetime(2030, 1, 7, 0, 0, tzinfo=UTC)
WINDOW = (WINDOW_START, WINDOW_START + timedelta(days=1))


def _item(starts_at: datetime, minutes: int = 30) -> GridItem:
    return GridItem(starts_at, starts_at + timedelta(minutes=minutes), ("line",), "", "", None)


def _inside(column: dict[str, object]) -> list[dict[str, object]]:
    inside = column["inside"]
    assert isinstance(inside, list)
    return inside


def _time_off(start_hour: int, end_hour: int, lines: tuple[str, ...] = ("band",)) -> GridItem:
    return GridItem(
        WINDOW_START + timedelta(hours=start_hour),
        WINDOW_START + timedelta(hours=end_hour),
        lines,
        "/x",
        "",
        None,
        behind=True,
    )


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


def returns_band_and_appointment_in_one_column_when_time_off_overlaps_an_appointment() -> None:
    band = _time_off(12, 14)
    appointment = _item(WINDOW_START + timedelta(hours=13))

    column = grid_column("Day", "Day", [band, appointment], WINDOW, ZONE)

    band_classes, appointment_classes = (str(each["classes"]) for each in _inside(column))
    assert "time-grid-behind time-grid-lane-1 time-grid-lanes-1" in band_classes
    assert "time-grid-front time-grid-over" in appointment_classes
    assert "time-grid-lane-1 time-grid-lanes-1" in appointment_classes


def returns_no_over_class_when_an_appointment_does_not_touch_the_band() -> None:
    clear = _item(WINDOW_START + timedelta(hours=13))

    column = grid_column("Day", "Day", [_time_off(12, 13), clear], WINDOW, ZONE)

    assert "time-grid-over" not in str(_inside(column)[1]["classes"])


def returns_last_lane_when_more_overlaps_than_the_limit() -> None:
    crowd = [_time_off(9, 10) for _ in range(10)]

    column = grid_column("Day", "Day", crowd, WINDOW, ZONE)

    classes = str(_inside(column)[9]["classes"]).split()
    assert "time-grid-lane-8" in classes and "time-grid-lane-9" not in classes
    assert "time-grid-lanes-8" in classes


def returns_three_visible_lines_when_block_is_one_row() -> None:
    lines = ("12:00 to 12:30", "Cardiology", "Ada Lovelace", "Room 1", "Booked")
    block = GridItem(
        WINDOW_START + timedelta(hours=12),
        WINDOW_START + timedelta(hours=12, minutes=30),
        lines,
        "/x",
        "",
        None,
    )

    column = grid_column("Day", "Day", [block], WINDOW, ZONE)

    assert _inside(column)[0]["fits"] == 3


def returns_all_words_in_the_spoken_text_when_reason_has_200_characters() -> None:
    reason = ("long " * 40).strip()
    off = _time_off(12, 13, ("12:00 to 13:00", "Time off", reason))

    column = grid_column("Day", "Day", [off], WINDOW, ZONE)

    assert _inside(column)[0]["spoken"] == f"12:00 to 13:00, Time off, {reason}"


def returns_every_line_fitting_when_the_item_is_outside_the_grid() -> None:
    early = GridItem(
        WINDOW_START + timedelta(hours=6),
        WINDOW_START + timedelta(hours=6, minutes=30),
        ("a", "b", "c", "d", "e"),
        "/x",
        "",
        None,
    )

    column = grid_column("Day", "Day", [early], WINDOW, ZONE)

    outside = column["outside"]
    assert isinstance(outside, list) and outside[0]["fits"] == 5


def returns_drawn_time_with_dash_and_spoken_time_with_to_when_the_first_line_is_a_span() -> None:
    start = WINDOW_START + timedelta(hours=8)
    item = GridItem(start, start + timedelta(minutes=30), ("08:00 to 08:30", "Visit"), "", "", None)

    [shown] = _inside(grid_column("Mon", "Monday", [item], WINDOW, ZONE))

    assert shown["drawn"] == ("08:00–08:30", "Visit")
    assert shown["spoken"] == "08:00 to 08:30, Visit"
