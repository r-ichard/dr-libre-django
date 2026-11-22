"""Task 17c, #25 and #30: no browser in the sandbox, so the alignment and containment of the time
grid are proved from the rendered markup and the style sheet. Pixels stay unmeasured."""

import re
from pathlib import Path

STYLE_SHEET = Path(__file__).resolve().parents[3] / "static" / "css" / "time-grid.css"
RULE = re.compile(r"([^{}@]+)\{([^{}]*)\}")
AXIS_ANCESTORS = {"", ".time-grid"}
AXIS_LAST_COMPOUNDS = {"ol", ".time-grid__axis"}
MINIMUM_OVERLAP_WIDTH_REM = 7


def _rules() -> list[tuple[str, dict[str, str]]]:
    """Every rule in source order, media queries flattened (the wide layout is the one proved)."""
    rules: list[tuple[str, dict[str, str]]] = []
    for selectors, body in RULE.findall(
        re.sub(r"/\*.*?\*/", "", STYLE_SHEET.read_text(), flags=re.S)
    ):
        declarations = dict(
            (name.strip(), value.strip())
            for name, _, value in (part.partition(":") for part in body.split(";") if ":" in part)
        )
        rules.extend((selector.strip(), declarations) for selector in selectors.split(","))
    return rules


def _specificity(selector: str) -> tuple[int, int]:
    classes = selector.count(".")
    elements = len([part for part in re.split(r"[ .]+", selector) if part and part == "ol"])
    return classes, elements


def _applies_to_axis(selector: str) -> bool:
    *ancestors, last = selector.split(" ")
    return last in AXIS_LAST_COMPOUNDS and " ".join(ancestors) in AXIS_ANCESTORS


def _winning_margin_top_of_axis() -> str:
    candidates = []
    for order, (selector, declarations) in enumerate(_rules()):
        if not _applies_to_axis(selector):
            continue
        for name in ("margin", "margin-top"):
            if name in declarations:
                value = declarations[name].split()[0]
                candidates.append((_specificity(selector), order, value))
    return max(candidates)[2]


def _declarations_of(selector: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for found, declarations in _rules():
        if found == selector:
            merged.update(declarations)
    return merged


def returns_axis_offset_equal_to_the_heading_height_when_cascade_is_applied() -> None:
    assert _winning_margin_top_of_axis() == "var(--heading-height)"


def returns_same_row_height_on_axis_rows_and_item_rows() -> None:
    assert _declarations_of(".time-grid-row")["height"] == "var(--row-height)"
    assert (
        "repeat(24, var(--row-height))"
        in _declarations_of(".time-grid__items")["grid-template-rows"]
    )
    assert _declarations_of(".time-grid__heading")["height"] == "var(--heading-height)"


def returns_no_padding_or_extra_margin_above_the_item_rows() -> None:
    items = _declarations_of(".time-grid__items")
    assert "padding" not in items and "margin" not in items and "margin-top" not in items
    assert _declarations_of(".time-grid-item")["margin"] == "1px 0"


def returns_a_row_class_for_every_row_once() -> None:
    names = [selector for selector, _ in _rules()]
    for number in range(1, 25):
        assert names.count(f".time-grid-at-{number}") == 1
        assert names.count(f".time-grid-span-{number}") == 1


def returns_overlaps_side_by_side_with_a_readable_minimum_width() -> None:
    columns = _declarations_of(".time-grid__items").get("grid-auto-columns", "")

    minimum = re.fullmatch(r"minmax\((\d+(?:\.\d+)?)rem, 1fr\)", columns)
    assert minimum is not None
    assert float(minimum.group(1)) >= MINIMUM_OVERLAP_WIDTH_REM


def returns_item_that_clips_and_wraps_what_does_not_fit() -> None:
    item = _declarations_of(".time-grid-item")

    assert item.get("min-width") == "0"
    assert item.get("overflow") == "hidden"
    assert item.get("overflow-wrap") == "anywhere"


def returns_empty_text_spanning_every_column_of_its_day() -> None:
    assert _declarations_of(".time-grid__none").get("grid-column") == "1 / -1"
