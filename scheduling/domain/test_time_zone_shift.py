"""Task 27b item 10, issue #36: a zone change shifts only the starts whose wall clock differs."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.time_zone_shift import shifted_starts, zone_change_sentence

BERLIN = ZoneInfo("Europe/Berlin")
PARIS = ZoneInfo("Europe/Paris")
AUCKLAND = ZoneInfo("Pacific/Auckland")
FIRST_START = datetime(2030, 1, 8, 6, 0, tzinfo=UTC)
SECOND_START = datetime(2030, 1, 9, 6, 0, tzinfo=UTC)


def returns_no_starts_when_old_and_new_zone_read_the_same_wall_clock() -> None:
    assert shifted_starts([FIRST_START], BERLIN, PARIS) == []


def returns_every_start_whose_wall_clock_differs_when_zone_changes() -> None:
    assert shifted_starts([FIRST_START, SECOND_START], BERLIN, AUCKLAND) == [
        FIRST_START,
        SECOND_START,
    ]


ONE_SENTENCE = (
    "1 upcoming appointment will show another local time. For example, "
    "Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read "
    "Tuesday 8 January 2030, 19:00 (Pacific/Auckland)."
)
TWO_SENTENCE = (
    "2 upcoming appointments will show another local time. For example, "
    "Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read "
    "Tuesday 8 January 2030, 19:00 (Pacific/Auckland)."
)


def returns_singular_sentence_with_the_first_start_as_example_when_one_shifts() -> None:
    assert zone_change_sentence([FIRST_START], BERLIN, AUCKLAND) == ONE_SENTENCE


def returns_plural_sentence_with_the_first_start_as_example_when_two_shift() -> None:
    assert zone_change_sentence([FIRST_START, SECOND_START], BERLIN, AUCKLAND) == TWO_SENTENCE
