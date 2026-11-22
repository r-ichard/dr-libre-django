"""Task 27d: the one rule that keeps a value PostgreSQL cannot carry out of a query."""

from scheduling.domain.fhir_common import carries_only_storable_text


def returns_false_only_when_text_holds_a_nul_character() -> None:
    assert carries_only_storable_text("a\x00b") is False
    assert carries_only_storable_text("\x00") is False
    assert carries_only_storable_text("") is True
    assert carries_only_storable_text("abc") is True
