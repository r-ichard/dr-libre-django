"""Section 16: a date of birth typed as day, month and year becomes one date or one error for
the group, so a person never meets three messages for one mistake."""

from datetime import date

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.visitor_rules import valid_birth_date

FIELD = "date_of_birth"
YEAR_DIGITS = 4
BIRTH_PARTS = ("date_of_birth_day", "date_of_birth_month", "date_of_birth_year")


def read_birth_date(
    day: str, month: str, year: str, today: date, required: bool
) -> Result[date | None]:
    if not (day or month or year):
        return _error("Enter your date of birth.") if required else Success(None)
    for text, name in ((day, "day"), (month, "month"), (year, "year")):
        if not text:
            return _error(f"Enter a {name}")
    if not all(part.isascii() and part.isdigit() for part in (day, month, year)):
        return _error("Use numbers only")
    if len(year) != YEAR_DIGITS:
        return _error("Enter a year with four digits")
    try:
        born = date(int(year), int(month), int(day))
    except ValueError:
        return _error("That date does not exist")
    if born >= today:
        return _error("A date of birth must be in the past")
    if not valid_birth_date(born, today):
        return _error("Enter a valid date of birth")
    return Success(born)


def _error(message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(FIELD, message)])
