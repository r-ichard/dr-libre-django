"""Section 9.4: a clinical note is at most 5000 characters after trimming."""

from scheduling.domain.failure import Failure, Success


def returns_note_when_5000_characters() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note("x" * 5000) == Success("x" * 5000)


def rejects_note_when_5001_characters() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    result = validate_clinical_note("x" * 5001)

    assert isinstance(result, Failure)
    assert result.details["fields"] == [
        {"field": "clinical_notes", "message": "Use at most 5000 characters."}
    ]


def returns_note_when_it_has_outer_whitespace() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note("  knee, left \n") == Success("knee, left")


def returns_empty_note_when_clinician_clears_it() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note("   ") == Success("")


def returns_trimmed_length_when_padding_would_exceed_limit() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note(" " * 10 + "x" * 5000) == Success("x" * 5000)
