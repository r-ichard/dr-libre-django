"""One rule for every whole number a write accepts, with the bounds of its column."""

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

SMALLINT_MAXIMUM = 32767


def check_whole_number(field: str, raw: str, minimum: int, maximum: int) -> Result[int]:
    """Digits only: no sign, no underscore, no non-ASCII digit; a `bool` never arrives as text."""
    text = raw.strip()
    too_small = f"Use a whole number of {minimum} or more."
    too_large = f"Use a whole number of at most {maximum}."
    if not (text.isascii() and text.isdigit()):
        return _refused(field, too_small)
    try:
        number = int(text)
    except ValueError:  # beyond Python's digit-count limit for int()
        return _refused(field, too_large)
    if number < minimum:
        return _refused(field, too_small)
    if number > maximum:
        return _refused(field, too_large)
    return Success(number)


def _refused(field: str, message: str) -> Failure:
    return Failure.invalid_input([FieldMessage(field, message)])
