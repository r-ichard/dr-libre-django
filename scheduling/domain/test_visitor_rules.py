"""Section 7.1 step 3: what a visitor may type about themselves."""

import importlib
from datetime import date
from types import ModuleType

import pytest

TODAY = date(2030, 1, 7)


def _rules() -> ModuleType:
    """Imported per test, so a module not written yet fails its tests and not the collection."""
    return importlib.import_module("scheduling.domain.visitor_rules")


def returns_false_when_birth_date_is_tomorrow() -> None:
    assert _rules().valid_birth_date(date(2030, 1, 8), TODAY) is False


def returns_true_when_birth_date_is_today() -> None:
    assert _rules().valid_birth_date(TODAY, TODAY) is True


def returns_true_when_person_turns_120_today() -> None:
    assert _rules().valid_birth_date(date(1910, 1, 7), TODAY) is True


def returns_false_when_person_would_be_120_and_one_day() -> None:
    assert _rules().valid_birth_date(date(1910, 1, 6), TODAY) is False


def returns_stripped_lower_case_when_email_is_normalised() -> None:
    assert _rules().normalise_email("  Ada.Byron@Example.TEST ") == "ada.byron@example.test"


@pytest.mark.parametrize(
    "address",
    [
        "a@b",
        "name@example",
        "na me@example.org",
        "a@@example.org",
        "a@b@example.org",
        "@example.org",
        "name@.org",
        "name@example.",
    ],
)
def returns_false_when_address_is_not_like_name_at_host_dot_domain(address: str) -> None:
    assert _rules().is_valid_email(address) is False


@pytest.mark.parametrize("address", ["name@example.org", "first.last+tag@mail.example.org"])
def returns_true_when_address_is_like_name_at_host_dot_domain(address: str) -> None:
    assert _rules().is_valid_email(address) is True


def returns_true_when_address_is_254_characters_and_false_at_255() -> None:
    suffix = "@example.org"
    longest = "a" * (254 - len(suffix)) + suffix

    assert _rules().is_valid_email(longest) is True
    assert _rules().is_valid_email("a" + longest) is False
