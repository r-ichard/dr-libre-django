"""Section 4: slot text in the hospital's zone."""

from datetime import UTC, datetime

SYDNEY_SLOT = datetime(2030, 12, 2, 23, 30, tzinfo=UTC)


def returns_local_time_on_the_next_day_when_slot_is_in_sydney() -> None:
    from scheduling.domain.slot_text import slot_visible_text

    text = slot_visible_text(SYDNEY_SLOT, "Australia/Sydney")

    assert text == "Tue 3 Dec, 10:30"


def returns_twenty_four_hour_clock_when_slot_is_in_the_afternoon() -> None:
    from scheduling.domain.slot_text import slot_visible_text

    afternoon = datetime(2030, 12, 3, 13, 5, tzinfo=UTC)

    assert slot_visible_text(afternoon, "Europe/Berlin") == "Tue 3 Dec, 14:05"
