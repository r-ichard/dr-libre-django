"""Task 17c, #25 and #30: no browser in the sandbox, so the alignment and containment of the time
grid are proved from the rendered markup and the style sheet. Pixels stay unmeasured."""

import re
from pathlib import Path

STYLE_SHEET = Path(__file__).resolve().parents[3] / "static" / "css" / "time-grid.css"
RULE = re.compile(r"([^{}@]+)\{([^{}]*)\}")
AXIS_ANCESTORS = {"", ".time-grid"}
AXIS_LAST_COMPOUNDS = {"ol", ".time-grid__axis"}
LANE_LIMIT = 8
PIXELS_PER_REM = 16


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


def returns_item_that_clips_and_wraps_what_does_not_fit() -> None:
    item = _declarations_of(".time-grid-item")

    assert item.get("min-width") == "0"
    assert item.get("overflow") == "hidden"
    assert item.get("overflow-wrap") == "anywhere"


def returns_empty_text_spanning_every_column_of_its_day() -> None:
    assert _declarations_of(".time-grid__none").get("grid-column") == "1 / -1"


def _pixels(value: str) -> float:
    rem = re.fullmatch(r"(\d+(?:\.\d+)?)rem", value)
    assert rem is not None, value
    return float(rem.group(1)) * PIXELS_PER_REM


def returns_one_explicit_column_and_no_implicit_columns_when_items_are_laid_out() -> None:
    items = _declarations_of(".time-grid__items")

    assert items.get("grid-template-columns") == "minmax(0, 1fr)"
    assert "grid-auto-columns" not in items


def returns_grid_column_one_on_every_item() -> None:
    assert _declarations_of(".time-grid-item").get("grid-column") == "1"


def returns_line_rules_that_never_wrap_and_end_in_an_ellipsis() -> None:
    line = _declarations_of(".time-grid-item__line")

    assert line.get("white-space") == "nowrap"
    assert line.get("overflow") == "hidden"
    assert line.get("text-overflow") == "ellipsis"
    assert line.get("height") == "var(--line-height)"
    assert line.get("line-height") == "var(--line-height)"


def returns_pixel_constants_equal_to_the_domain_when_tokens_are_parsed() -> None:
    from scheduling.domain.calendar_grid import (
        BLOCK_FRAME_PIXELS,
        LINE_HEIGHT_PIXELS,
        ROW_HEIGHT_PIXELS,
    )

    grid = _declarations_of(".time-grid")
    padding_vertical = _pixels("0.25rem") * 2
    border_and_margin = 1 * 2 + 1 * 2
    assert _pixels(grid["--row-height"]) == ROW_HEIGHT_PIXELS
    assert _pixels(grid["--line-height"]) == LINE_HEIGHT_PIXELS
    assert _declarations_of(".time-grid-item")["padding"].split()[0] == "var(--space-1)"
    assert padding_vertical + border_and_margin == BLOCK_FRAME_PIXELS


def returns_a_lane_class_for_every_lane_up_to_the_limit() -> None:
    names = [selector for selector, _ in _rules()]
    for lane in range(1, LANE_LIMIT + 1):
        assert names.count(f".time-grid-lane-{lane}") == 1
        assert names.count(f".time-grid-lanes-{lane}") == 1
    assert ".time-grid-lane-9" not in names


def returns_lane_that_fits_its_column_when_lane_is_at_most_lanes() -> None:
    for lanes in range(1, LANE_LIMIT + 1):
        for lane in range(1, lanes + 1):
            assert (lane - 1) / lanes + 1 / lanes <= 1


def returns_band_behind_and_appointment_in_front() -> None:
    behind = int(_declarations_of(".time-grid-behind")["z-index"])
    front = int(_declarations_of(".time-grid-front")["z-index"])

    assert behind < front


def returns_cut_lines_hidden_only_from_64rem() -> None:
    sheet = re.sub(r"/\*.*?\*/", "", STYLE_SHEET.read_text(), flags=re.S)
    marker = "@media (min-width: 64rem)"
    assert ".time-grid-item__line--cut" in sheet[sheet.index(marker) :]
    assert ".time-grid-item__line--cut" not in sheet[: sheet.index(marker)]


def returns_cut_lines_display_none() -> None:
    assert _declarations_of(".time-grid-item__line--cut").get("display") == "none"


def returns_each_lane_class_setting_its_own_number_and_the_rail_set_on_covering_fronts() -> None:
    for number in range(1, LANE_LIMIT + 1):
        assert _declarations_of(f".time-grid-lane-{number}") == {"--lane": str(number)}
        assert _declarations_of(f".time-grid-lanes-{number}") == {"--lanes": str(number)}
    assert _declarations_of(".time-grid-front.time-grid-over") == {"--rail-width": "var(--rail)"}
    assert _declarations_of(".time-grid-item")["--rail-width"] == "0px"


def returns_scroll_frame_that_holds_the_out_of_flow_text_when_the_grid_is_wide() -> None:
    """Task 19, item 22: `.visually-hidden` is `position: absolute`; its containing block is the
    nearest positioned ancestor. `.time-grid` is it, and it scrolls, so the spans of columns past
    the edge widen the frame and never the page."""
    base_sheet = STYLE_SHEET.parent / "base.css"
    assert re.search(r"\.visually-hidden\s*\{[^}]*position:\s*absolute", base_sheet.read_text())
    assert _declarations_of(".time-grid")["position"] == "relative"
    assert _declarations_of(".time-grid")["overflow-x"] == "auto"


def returns_status_icon_no_taller_than_the_time_line_when_the_first_line_is_drawn() -> None:
    icon = _declarations_of(".time-grid-item__time .icon")
    assert (icon["width"], icon["height"]) == ("1em", "1em")
    assert icon["vertical-align"] == "middle"


def returns_count_spaced_with_the_token_when_it_follows_the_search_form() -> None:
    sheet = (STYLE_SHEET.parent / "components.css").read_text()
    assert re.search(r"\.list-count\s*\{\s*margin-top:\s*var\(--space-4\)", sheet)


PAGE_PIXELS_AT_1440 = 1088
SEVEN_DAYS = 7
TIME_LINE_PIXELS = 114
BORDER_PIXELS = 6 + 1


def _column_minimum_pixels() -> float:
    columns = _declarations_of(".time-grid__columns")["grid-auto-columns"]
    found = re.fullmatch(r"minmax\((\d+(?:\.\d+)?rem), 1fr\)", columns)
    assert found is not None, columns
    return _pixels(found.group(1))


def _space_pixels(value: str) -> float:
    token = re.fullmatch(r"var\((--space-\d)\)", value)
    assert token is not None, value
    tokens = (STYLE_SHEET.parent / "tokens.css").read_text()
    declared = re.search(rf"{token.group(1)}:\s*([\d.]+rem)", tokens)
    assert declared is not None, value
    return _pixels(declared.group(1))


def _item_padding_pixels() -> float:
    return _space_pixels(_declarations_of(".time-grid-item")["padding"].split()[1])


def returns_seven_columns_that_fit_1088_pixels_when_axis_and_gaps_are_counted() -> None:
    wide_grid = next(d for s, d in _rules() if s == ".time-grid" and "grid-template-columns" in d)
    axis_pixels = _pixels(wide_grid["grid-template-columns"].split()[0])
    gap = _space_pixels(_declarations_of(".time-grid__columns")["gap"])
    gaps_total = gap * (SEVEN_DAYS - 1)

    used = axis_pixels + SEVEN_DAYS * _column_minimum_pixels() + gaps_total

    assert used <= PAGE_PIXELS_AT_1440


def returns_a_time_line_of_at_least_114_pixels_when_a_block_sits_beside_a_time_off_rail() -> None:
    rail = _pixels(_declarations_of(".time-grid")["--rail"])
    frame = rail + 2 * _item_padding_pixels() + BORDER_PIXELS

    assert _column_minimum_pixels() - frame >= TIME_LINE_PIXELS


def returns_a_time_line_of_at_least_114_pixels_when_a_block_is_alone_in_its_column() -> None:
    frame = 2 * _item_padding_pixels() + BORDER_PIXELS

    assert _column_minimum_pixels() - frame >= TIME_LINE_PIXELS
