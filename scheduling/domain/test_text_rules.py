"""Task 27a, finding #38: one text rule for every text a write accepts."""

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success

MESSAGE = 'Remove the character after "a".'
LINE_BREAK_MESSAGE = 'This field takes one line. Remove the line break after "a".'
NOT_STORABLE = [
    "a\x00b",
    "a\x01b",
    "a\x0bb",
    "a\x0cb",
    "a\x1fb",
    "a\x7fb",
    "a\x85b",
    "a\x9fb",
    "a\ud800b",
]


def _refused(field: str, message: str = MESSAGE) -> Failure:
    return Failure.invalid_input([FieldMessage(field, message)])


@pytest.mark.parametrize("text", NOT_STORABLE)
def returns_refusal_when_free_text_has_control_character(text: str) -> None:
    from scheduling.domain.text_rules import check_storable_text

    assert check_storable_text("reason", text, single_line=False) == _refused("reason")


@pytest.mark.parametrize("text", NOT_STORABLE)
def returns_refusal_when_single_line_text_has_control_character(text: str) -> None:
    from scheduling.domain.text_rules import check_storable_text

    assert check_storable_text("title", text, single_line=True) == _refused("title")


@pytest.mark.parametrize("text", ["a\nb", "a\rb", "a\tb"])
def returns_one_line_refusal_when_single_line_text_has_line_break_or_tab(text: str) -> None:
    from scheduling.domain.text_rules import check_storable_text

    result = check_storable_text("title", text, single_line=True)

    assert result == _refused("title", LINE_BREAK_MESSAGE)


def returns_text_when_free_text_has_line_break_and_tab() -> None:
    from scheduling.domain.text_rules import check_storable_text

    text = "line one\r\n\tline two"

    assert check_storable_text("reason", text, single_line=False) == Success(text)


def returns_text_when_it_holds_accents_and_emoji() -> None:
    from scheduling.domain.text_rules import check_storable_text

    text = "Zoë – 患者 🩺"

    assert check_storable_text("name", text, single_line=True) == Success(text)


def returns_refusal_on_clinical_notes_when_note_has_nul_byte() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note("knee\x00left") == _refused(
        "clinical_notes", 'Remove the character after "knee".'
    )


def returns_note_when_it_has_line_breaks() -> None:
    from scheduling.domain.clinical_note_rules import validate_clinical_note

    assert validate_clinical_note("knee\n\tleft") == Success("knee\n\tleft")


def returns_refusal_on_reason_when_time_off_reason_has_nul_byte() -> None:
    from datetime import UTC, datetime

    from scheduling.domain.time_off_rules import time_off_failures

    start = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
    end = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)

    failures = time_off_failures(start, end, "sick\x00", [])

    assert failures == [FieldMessage("reason", 'Remove the character after "sick".')]


def returns_refusal_on_title_when_title_has_control_character() -> None:
    from scheduling.domain.clinician_rules import check_title

    assert check_title("Dr\x07") == _refused("title", 'Remove the character after "Dr".')


def returns_text_when_it_holds_no_break_space_just_past_the_control_range() -> None:
    from scheduling.domain.text_rules import check_storable_text

    assert check_storable_text("reason", "a\xa0b", single_line=True) == Success("a\xa0b")


def returns_message_with_words_before_and_no_character_when_text_has_a_form_feed() -> None:
    from scheduling.domain.text_rules import check_storable_text

    result = check_storable_text("clinical_notes", "Dear doctor\x0cthanks", single_line=False)

    assert result == Failure.invalid_input(
        [FieldMessage("clinical_notes", 'Remove the character after "Dear doctor".')]
    )


def returns_message_at_start_when_first_character_is_refused() -> None:
    from scheduling.domain.text_rules import check_storable_text

    result = check_storable_text("reason", "\x0bhello", single_line=False)

    assert result == Failure.invalid_input(
        [FieldMessage("reason", "Remove the character at the start of the text.")]
    )


def returns_one_line_message_when_single_line_text_has_a_line_break() -> None:
    from scheduling.domain.text_rules import check_storable_text

    result = check_storable_text("name", "Saint\nAnne", single_line=True)

    assert result == Failure.invalid_input(
        [FieldMessage("name", 'This field takes one line. Remove the line break after "Saint".')]
    )


def returns_trimmed_text_with_lines_when_check_text_is_free() -> None:
    from scheduling.domain.record_fields import check_text

    result = check_text("bio", " one\r\n\r\n\ttwo ", 2000, None, single_line=False)

    assert result == Success("one\r\n\r\n\ttwo")


def returns_message_quoting_only_the_last_twenty_characters_when_text_before_is_long() -> None:
    from scheduling.domain.text_rules import check_storable_text

    text = "x" * 30 + "0123456789abcdefghij" + "\x0c"

    result = check_storable_text("clinical_notes", text, single_line=False)

    assert result == Failure.invalid_input(
        [FieldMessage("clinical_notes", 'Remove the character after "0123456789abcdefghij".')]
    )
