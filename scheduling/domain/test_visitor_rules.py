"""Section 7.1 step 3: what a visitor may type about themselves."""

import importlib
from datetime import date
from types import ModuleType

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
