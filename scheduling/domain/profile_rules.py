"""Task 15: the format rules of the patient profile and of a new password."""

import re
from datetime import date

from scheduling.domain.failure import FieldMessage

PHONE_PATTERN = re.compile(r"[0-9 +()\-]{7,20}")
PASSWORD_MINIMUM = 10
PASSWORD_MAXIMUM = 72


def phone_failure(text: str) -> FieldMessage | None:
    if text == "" or PHONE_PATTERN.fullmatch(text):
        return None
    return FieldMessage("phone", "Enter 7 to 20 characters: digits, spaces and the signs + ( ) -.")


def birth_date_failure(born: date, today: date) -> FieldMessage | None:
    if born > today:
        return FieldMessage("date_of_birth", "The date of birth cannot be in the future.")
    return None


def new_password_failures(current: str, new: str) -> list[FieldMessage]:
    if not PASSWORD_MINIMUM <= len(new) <= PASSWORD_MAXIMUM:
        message = f"Use {PASSWORD_MINIMUM} to {PASSWORD_MAXIMUM} characters."
        return [FieldMessage("new_password", message)]
    if new == current:
        return [FieldMessage("new_password", "Choose a password different from the current one.")]
    return []
