"""Every whole number has the bounds of its column."""

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success

SMALLINT_MAXIMUM = 32767
WEIGHT_MESSAGE = "Use a whole number of at most 32767."


def _weight(raw: str) -> object:
    from scheduling.domain.clinician_rules import check_weight

    return check_weight(raw)


def returns_weight_when_it_is_the_largest_smallint() -> None:
    assert _weight("32767") == Success(SMALLINT_MAXIMUM)


@pytest.mark.parametrize("raw", ["32768", "40000", "99999999999", "1" + "0" * 40])
def returns_refusal_on_weight_field_when_weight_is_above_the_column(raw: str) -> None:
    assert _weight(raw) == Failure.invalid_input(
        [FieldMessage("round_robin_weight", WEIGHT_MESSAGE)]
    )


@pytest.mark.parametrize(
    ("check", "field"),
    [
        ("check_capacity", "capacity"),
        ("check_duration_minutes", "duration_minutes"),
        ("check_buffer_minutes", "buffer_minutes"),
    ],
)
def returns_refusal_on_field_when_record_number_is_above_the_column(check: str, field: str) -> None:
    from scheduling.domain import record_fields

    result = getattr(record_fields, check)("32768")

    assert result == Failure.invalid_input([FieldMessage(field, WEIGHT_MESSAGE)])


def returns_the_number_when_record_number_is_the_largest_smallint() -> None:
    from scheduling.domain.record_fields import check_capacity

    assert check_capacity("32767") == Success(SMALLINT_MAXIMUM)


@pytest.mark.parametrize("raw", ["0", "-1", "+5", "1_0", "\u0663", "\uff11", "", "1.5"])
def returns_refusal_on_weight_field_when_text_is_not_a_whole_number_of_one_or_more(
    raw: str,
) -> None:
    assert _weight(raw) == Failure.invalid_input(
        [FieldMessage("round_robin_weight", "Use a whole number of 1 or more.")]
    )


def returns_weight_when_digits_have_surrounding_spaces() -> None:
    assert _weight(" 7 ") == Success(7)


def returns_weight_of_one_when_it_is_the_smallest_allowed() -> None:
    assert _weight("1") == Success(1)


def returns_refusal_on_weight_field_when_digits_exceed_the_interpreter_conversion_limit() -> None:
    assert _weight("9" * 5000) == Failure.invalid_input(
        [FieldMessage("round_robin_weight", WEIGHT_MESSAGE)]
    )
