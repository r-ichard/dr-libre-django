"""Three typed parts of a date of birth become one date or one error for the group."""

from datetime import date

import pytest

from scheduling.domain.date_parts import read_birth_date
from scheduling.domain.failure import Failure, FieldMessage, Success

TODAY = date(2030, 3, 15)


def _error(message: str) -> Failure:
    return Failure.invalid_input([FieldMessage("date_of_birth", message)])


def _read(day: str, month: str, year: str, required: bool = True) -> object:
    return read_birth_date(day, month, year, TODAY, required)


@pytest.mark.parametrize(
    ("parts", "message"),
    [
        (("", "3", ""), "Enter a day"),
        (("", "", "1985"), "Enter a day"),
        (("14", "", ""), "Enter a month"),
        (("", "3", "1985"), "Enter a day"),
        (("14", "", "1985"), "Enter a month"),
        (("14", "3", ""), "Enter a year"),
        (("31", "4", "1990"), "That date does not exist"),
        (("29", "2", "1990"), "That date does not exist"),
        (("14", "3", "85"), "Enter a year with four digits"),
        (("15", "3", "2030"), "A date of birth must be in the past"),
        (("16", "3", "2030"), "A date of birth must be in the past"),
        (("14", "3", "1909"), "Enter a valid date of birth"),
    ],
)
def returns_one_error_naming_the_problem_when_a_part_is_wrong(
    parts: tuple[str, str, str], message: str
) -> None:
    assert _read(*parts) == _error(message)


@pytest.mark.parametrize("bad", ["a1", "-1", " 1", "１"])
def returns_use_numbers_only_when_a_part_holds_other_characters(bad: str) -> None:
    assert _read(bad, "3", "1985") == _error("Use numbers only")


def returns_the_leap_day_when_year_is_2000_and_date_is_29_february() -> None:
    assert _read("29", "2", "2000") == Success(date(2000, 2, 29))


def returns_the_date_when_year_is_exactly_120_years_back() -> None:
    assert _read("15", "3", "1910") == Success(date(1910, 3, 15))


def returns_none_when_all_three_are_empty_and_not_required() -> None:
    assert _read("", "", "", required=False) == Success(None)


def returns_enter_your_date_of_birth_when_all_three_are_empty_and_required() -> None:
    assert _read("", "", "") == _error("Enter your date of birth.")
