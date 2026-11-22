"""Section 13: a spreadsheet must never read an exported cell as a formula. Pure."""

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def escape_cell(cell: str) -> str:
    return f"'{cell}" if cell.startswith(FORMULA_STARTS) else cell


def csv_row(cells: list[str]) -> list[str]:
    return [escape_cell(cell) for cell in cells]
