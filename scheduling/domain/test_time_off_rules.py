"""Section 9.3: time off needs an end after its start, a short reason and a period not yet kept."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.failure import FieldMessage

START = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
END = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)


def _failures(
    starts: datetime = START,
    ends: datetime = END,
    reason: str = "",
    existing: tuple[tuple[datetime, datetime], ...] = (),
) -> list[FieldMessage]:
    from scheduling.domain.time_off_rules import time_off_failures

    return time_off_failures(starts, ends, reason, list(existing))


def rejects_time_off_when_end_not_after_start() -> None:
    assert [item.field for item in _failures(ends=START)] == ["ends_at"]


def rejects_reason_of_201_characters() -> None:
    assert [item.field for item in _failures(reason="x" * 201)] == ["reason"]


def returns_accepts_reason_of_200_characters() -> None:
    assert _failures(reason="x" * 200) == []


def rejects_time_off_when_identical_period_exists() -> None:
    assert [item.field for item in _failures(existing=((START, END),))] == ["starts_at"]


def returns_accepts_period_shifted_by_one_minute() -> None:
    shifted = (START + timedelta(minutes=1), END + timedelta(minutes=1))

    assert _failures(existing=(shifted,)) == []


def _inside(*spans: tuple[str, datetime, datetime, str]) -> list[str]:
    from scheduling.domain.time_off_rules import PlannedVisit, appointments_inside

    visits = [PlannedVisit(name, start, end, status) for name, start, end, status in spans]
    return [visit.label for visit in appointments_inside(START, END, visits)]


def returns_lists_appointment_when_inside_period() -> None:
    inside = ("a", START + timedelta(minutes=30), START + timedelta(hours=1), "BOOKED")

    assert _inside(inside) == ["a"]


def returns_lists_appointment_when_it_overlaps_the_period_start() -> None:
    assert _inside(
        ("a", START - timedelta(minutes=10), START + timedelta(minutes=10), "BOOKED")
    ) == ["a"]


def returns_skips_cancelled_appointment() -> None:
    assert _inside(("a", START, START + timedelta(minutes=30), "CANCELLED")) == []


def returns_skips_appointment_touching_end() -> None:
    assert _inside(("a", END, END + timedelta(minutes=30), "BOOKED")) == []


def returns_skips_appointment_ending_at_start() -> None:
    assert _inside(("a", START - timedelta(minutes=30), START, "BOOKED")) == []


def returns_no_failure_when_the_reason_holds_a_line_break() -> None:
    assert _failures(reason="Back\nsoon") == []


def returns_end_and_reason_failures_when_both_are_wrong() -> None:
    assert [item.field for item in _failures(ends=START, reason="a\x00b")] == ["ends_at", "reason"]
