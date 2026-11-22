"""Section 9.4: a clinical note is at most 5000 characters after trimming."""

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.text_rules import check_storable_text

CLINICAL_NOTE_MAXIMUM = 5000
FIELD = "clinical_notes"


def validate_clinical_note(text: str) -> Result[str]:
    trimmed = text.strip()
    unstorable = check_storable_text(FIELD, trimmed, single_line=False)
    if isinstance(unstorable, Failure):
        return unstorable
    if len(trimmed) > CLINICAL_NOTE_MAXIMUM:
        message = f"Use at most {CLINICAL_NOTE_MAXIMUM} characters."
        return Failure.invalid_input([FieldMessage(FIELD, message)])
    return Success(trimmed)
