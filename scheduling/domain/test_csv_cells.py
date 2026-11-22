"""Task 21, #9: a spreadsheet must never read an exported cell as a formula."""

import pytest


@pytest.mark.parametrize("trigger", ["=", "+", "-", "@", "\t", "\r"])
def returns_prefixes_apostrophe_when_cell_starts_with_formula_character(trigger: str) -> None:
    from scheduling.domain.csv_cells import escape_cell

    assert escape_cell(f"{trigger}SUM(A1)") == f"'{trigger}SUM(A1)"


def returns_leaves_plain_empty_and_inner_trigger_cells_unchanged() -> None:
    from scheduling.domain.csv_cells import escape_cell

    assert escape_cell("BOOKED") == "BOOKED"
    assert escape_cell("") == ""
    assert escape_cell("a=b+c-d@e") == "a=b+c-d@e"
    assert escape_cell(" =1") == " =1"


def returns_leaves_iso_instant_unchanged() -> None:
    from scheduling.domain.csv_cells import escape_cell

    assert escape_cell("2026-03-10T12:00:00Z") == "2026-03-10T12:00:00Z"


def returns_escapes_every_cell_of_a_row() -> None:
    from scheduling.domain.csv_cells import csv_row

    assert csv_row(["=1", "ok", "+2", "", "@x"]) == ["'=1", "ok", "'+2", "", "'@x"]
