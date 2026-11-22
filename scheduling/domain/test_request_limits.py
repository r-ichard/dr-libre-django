from datetime import UTC, date, datetime

import pytest

from scheduling.domain.request_limits import (
    MAXIMUM_BODY_BYTES,
    MAXIMUM_FIELDS,
    MAXIMUM_JSON_DEPTH,
    MAXIMUM_PAGE,
    day_in_range,
    declared_length,
    instant_in_range,
    json_depth,
    query_field_count,
)


def returns_depth_of_nested_brackets_when_scanning() -> None:
    assert json_depth(b"[" * 20 + b"]" * 20) == MAXIMUM_JSON_DEPTH
    assert json_depth(b"[" * 21 + b"]" * 21) == MAXIMUM_JSON_DEPTH + 1


def returns_zero_depth_when_brackets_sit_inside_strings() -> None:
    assert json_depth(b'{"a": "[[[ \\" [["}') == 1


def returns_the_number_when_length_is_a_non_negative_integer() -> None:
    assert declared_length("") == 0
    assert declared_length("0") == 0
    assert declared_length(str(MAXIMUM_BODY_BYTES)) == MAXIMUM_BODY_BYTES
    assert declared_length(str(MAXIMUM_BODY_BYTES + 1)) == MAXIMUM_BODY_BYTES + 1


@pytest.mark.parametrize("header", ["abc", "-1", "1.5", " ", "١٢"])
def returns_none_when_length_is_not_a_non_negative_integer(header: str) -> None:
    assert declared_length(header) is None


def returns_field_count_when_query_has_fields() -> None:
    assert query_field_count("") == 0
    assert query_field_count("a=1") == 1
    assert query_field_count("&".join(["a=1"] * MAXIMUM_FIELDS)) == MAXIMUM_FIELDS
    assert query_field_count("&".join(["a=1"] * (MAXIMUM_FIELDS + 1))) == MAXIMUM_FIELDS + 1


def returns_true_only_between_2000_and_2099_when_checking_instants() -> None:
    assert instant_in_range(datetime(2000, 1, 1, tzinfo=UTC))
    assert not instant_in_range(datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC))
    assert instant_in_range(datetime(2099, 12, 31, 23, 59, 59, tzinfo=UTC))
    assert not instant_in_range(datetime(2100, 1, 1, tzinfo=UTC))


def returns_true_only_between_2000_and_2099_when_checking_days() -> None:
    assert day_in_range(date(2000, 1, 1))
    assert not day_in_range(date(1999, 12, 31))
    assert day_in_range(date(2099, 12, 31))
    assert not day_in_range(date(2100, 1, 1))


def returns_one_million_when_reading_the_page_limit() -> None:
    assert MAXIMUM_PAGE == 1_000_000


@pytest.mark.parametrize(
    ("raw", "depth"),
    [(b"[1,[2]]", 2), (b"[][[]]", 2), (b"[[],[[]]]", 3), (b"{}", 1), (b"", 0)],
)
def returns_deepest_nesting_when_brackets_open_and_close_in_turn(raw: bytes, depth: int) -> None:
    assert json_depth(raw) == depth
