from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scheduling.domain.calendar_event import CalendarEvent


def _event(**overrides: object) -> CalendarEvent:
    from scheduling.domain.calendar_event import CalendarEvent

    return replace(
        CalendarEvent(
            uid="3f2c@drlibre",
            starts_at=datetime(2030, 1, 7, 10, 0, tzinfo=UTC),
            ends_at=datetime(2030, 1, 7, 10, 30, tzinfo=UTC),
            stamped_at=datetime(2030, 1, 7, 6, 0, tzinfo=UTC),
            summary="Dr Ada Byron: Check-up",
            location="Riverside Hospital, 1 River Road",
        ),
        **overrides,  # type: ignore[arg-type]
    )


def _text(**overrides: object) -> str:
    from scheduling.domain.calendar_event import build_calendar_text

    text: str = build_calendar_text(_event(**overrides))
    return text


def returns_utc_start_and_end_summary_and_location_when_event_is_built() -> None:
    lines = _text().split("\r\n")

    assert "DTSTART:20300107T100000Z" in lines
    assert "DTEND:20300107T103000Z" in lines
    assert "DTSTAMP:20300107T060000Z" in lines
    assert "UID:3f2c@drlibre" in lines
    assert "SUMMARY:Dr Ada Byron: Check-up" in lines
    assert "LOCATION:Riverside Hospital\\, 1 River Road" in lines


def returns_no_description_when_event_is_built() -> None:
    assert "DESCRIPTION" not in _text()


def returns_calendar_wrapper_lines_when_event_is_built() -> None:
    lines = _text().split("\r\n")

    assert lines[:3] == ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DrLibre//Booking//EN"]
    assert lines[-3:] == ["END:VEVENT", "END:VCALENDAR", ""]


def returns_escaped_comma_semicolon_backslash_and_newline_in_text() -> None:
    assert "SUMMARY:a\\,b\;c\\\\d\\ne\r\n" in _text(summary="a,b;c\\d\ne")


def returns_folded_lines_longer_than_75_octets_with_a_leading_space() -> None:
    lines = _text(location="x" * 100).split("\r\n")

    start = lines.index("LOCATION:" + "x" * 66)
    assert lines[start + 1] == " " + "x" * 34
    assert all(len(line.encode()) <= 75 for line in lines)


def returns_crlf_at_the_end_of_every_line() -> None:
    text = _text()

    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")


def returns_every_line_at_most_75_octets_when_a_line_folds_three_times() -> None:
    lines = _text(location="x" * 200).split("\r\n")

    start = lines.index("LOCATION:" + "x" * 66)
    assert lines[start + 1] == " " + "x" * 74
    assert lines[start + 2] == " " + "x" * 60


def returns_one_escaped_newline_when_text_has_a_carriage_return_and_line_feed() -> None:
    assert "SUMMARY:a\\nb\r\n" in _text(summary="a\r\nb")


def returns_begin_vevent_in_capitals_when_event_is_built() -> None:
    assert "BEGIN:VEVENT\r\n" in _text()
