"""Task 27a: one rule for every text a write accepts."""

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

NOT_STORABLE_MESSAGE = "Remove the character that cannot be saved."
LINE_BREAK_AND_TAB = frozenset("\t\n\r")
SURROGATES = range(0xD800, 0xE000)
WORDS_SHOWN = 20


def check_storable_text(field: str, raw: str, *, single_line: bool) -> Result[str]:
    """Refuses what PostgreSQL or a page cannot carry: NUL, other controls, lone surrogates.

    Free text keeps tab and line breaks; a single line refuses them too. The message says where
    the character is, by the words before it, and never echoes it."""
    for position, character in enumerate(raw):
        if _is_refused(character, single_line):
            message = _message(raw[:position], character in LINE_BREAK_AND_TAB)
            return Failure.invalid_input([FieldMessage(field, message)])
    return Success(raw)


def storable_search(raw: str) -> str:
    """A search text is trimmed; one that cannot be stored searches for nothing."""
    checked = check_storable_text("q", raw, single_line=False)
    return checked.value.strip() if isinstance(checked, Success) else ""


def _message(before: str, is_line_break: bool) -> str:
    context = before.strip()[-WORDS_SHOWN:].strip()
    what = "line break" if is_line_break else "character"
    where = f'after "{context}"' if context else "at the start of the text"
    prefix = "This field takes one line. " if is_line_break else ""
    return f"{prefix}Remove the {what} {where}."


def _is_refused(character: str, single_line: bool) -> bool:
    code = ord(character)
    if character in LINE_BREAK_AND_TAB:
        return single_line
    return code < 0x20 or 0x7F <= code <= 0x9F or code in SURROGATES
