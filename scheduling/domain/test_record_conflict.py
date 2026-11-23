"""Section 10: which fields the conflict page lists, and what each row holds. The truth
table of the plan, one case per row; what the admin read may be unknown (the form posted no
`read_` key), which is its own value and never an empty string."""

import pytest

from scheduling.domain.record_conflict import (
    FieldConflict,
    ReadKnown,
    ReadUnknown,
    ReadValue,
    conflicting_fields,
)

LABELS = {"name": "Name"}


def _rows(read: ReadValue, stored: str, typed: str) -> list[FieldConflict]:
    return conflicting_fields(LABELS, {"name": read}, {"name": stored}, {"name": typed})


def returns_no_row_when_read_stored_and_typed_are_equal() -> None:
    assert _rows(ReadKnown("Before"), "Before", "Before") == []


def returns_the_row_when_only_the_admin_changed_the_field() -> None:
    assert _rows(ReadKnown("Before"), "Before", "Second admin") == [
        FieldConflict("name", "Name", ReadKnown("Before"), "Before", "Second admin")
    ]


def returns_the_row_when_another_admin_changed_it_and_the_typed_value_equals_the_stored_one() -> (
    None
):
    assert _rows(ReadKnown("Before"), "First admin", "First admin") == [
        FieldConflict("name", "Name", ReadKnown("Before"), "First admin", "First admin")
    ]


def returns_the_row_with_three_values_when_all_three_differ() -> None:
    assert _rows(ReadKnown("Before"), "First admin", "Second admin") == [
        FieldConflict("name", "Name", ReadKnown("Before"), "First admin", "Second admin")
    ]


def returns_no_row_when_the_read_value_is_unknown_and_typed_equals_stored() -> None:
    assert _rows(ReadUnknown(), "Same", "Same") == []


def returns_the_row_with_an_unknown_read_value_when_typed_differs_from_stored() -> None:
    assert _rows(ReadUnknown(), "First admin", "Second admin") == [
        FieldConflict("name", "Name", ReadUnknown(), "First admin", "Second admin")
    ]


def returns_unknown_for_a_field_with_no_read_entry() -> None:
    rows = conflicting_fields(LABELS, {}, {"name": "First admin"}, {"name": "Second admin"})

    assert rows == [FieldConflict("name", "Name", ReadUnknown(), "First admin", "Second admin")]


def returns_only_the_fields_that_differ_in_label_order() -> None:
    labels = {"name": "Name", "city": "City", "phone": "Phone"}
    read = {"name": ReadKnown("a"), "city": ReadKnown("b"), "phone": ReadKnown("c")}
    stored = {"name": "a", "city": "b2", "phone": "c"}
    typed = {"name": "a", "city": "b3", "phone": "c9"}

    rows = conflicting_fields(labels, read, stored, typed)

    assert [row.field for row in rows] == ["city", "phone"]


@pytest.mark.parametrize("text", ["", "Zoë <b>", "x" * 300])
def returns_the_read_text_unchanged_when_it_is_known(text: str) -> None:
    assert _rows(ReadKnown(text), "stored", "typed") == [
        FieldConflict("name", "Name", ReadKnown(text), "stored", "typed")
    ]
