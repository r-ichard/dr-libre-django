"""Task 15: the format rules of the patient profile and of a new password."""

from datetime import date

import pytest

from scheduling.domain.failure import FieldMessage
from scheduling.domain.profile_rules import birth_date_failure, new_password_failures, phone_failure

TODAY = date(2030, 3, 15)
CURRENT = "current-password-1"


def returns_no_failure_when_phone_is_empty() -> None:
    assert phone_failure("") is None


@pytest.mark.parametrize("phone", ["1234567", "1" * 20, "+33 (0)1-23 45 67"])
def returns_no_failure_when_phone_is_allowed(phone: str) -> None:
    assert phone_failure(phone) is None


@pytest.mark.parametrize("phone", ["123456", "1" * 21, "0123 456 78a", "0123.456.789"])
def returns_failure_on_phone_field_when_phone_is_not_allowed(phone: str) -> None:
    assert phone_failure(phone) == FieldMessage(
        "phone", "Enter 7 to 20 characters: digits, spaces and the signs + ( ) -."
    )


def returns_failure_when_birth_date_is_tomorrow() -> None:
    assert birth_date_failure(date(2030, 3, 16), TODAY) == FieldMessage(
        "date_of_birth", "The date of birth cannot be in the future."
    )


@pytest.mark.parametrize("born", [TODAY, date(1990, 2, 28)])
def returns_no_failure_when_birth_date_is_not_in_the_future(born: date) -> None:
    assert birth_date_failure(born, TODAY) is None


@pytest.mark.parametrize("length", [10, 72])
def returns_no_failure_when_new_password_length_is_inside_the_range(length: int) -> None:
    assert new_password_failures(CURRENT, "n" * length) == []


@pytest.mark.parametrize("length", [9, 73])
def returns_failure_on_new_password_when_length_is_outside_the_range(length: int) -> None:
    assert new_password_failures(CURRENT, "n" * length) == [
        FieldMessage("new_password", "Use 10 to 72 characters.")
    ]


def returns_failure_when_new_password_equals_current() -> None:
    assert new_password_failures(CURRENT, CURRENT) == [
        FieldMessage("new_password", "Choose a password different from the current one.")
    ]
