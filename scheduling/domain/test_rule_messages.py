"""Section 9.3: the sentence shown for each refused rule, and a visit at this instant."""

from datetime import UTC, datetime, time, timedelta

from scheduling.domain.availability_rules import RoomChoice, RuleTimes, rule_failures
from scheduling.domain.failure import FieldMessage
from scheduling.domain.patient_directory import last_and_next_visit
from scheduling.domain.time_off_rules import time_off_failures

MONDAY = 1
NOON = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)
SOUND = RuleTimes(MONDAY, time(9, 0), time(12, 0), 15)


def _with(**changes: object) -> RuleTimes:
    fields = {**SOUND.__dict__, **changes}
    return RuleTimes(**fields)


def returns_sentence_for_weekday_outside_the_week() -> None:
    assert rule_failures(_with(weekday=7), None, []) == [
        FieldMessage("weekday", "Choose a day of the week.")
    ]


def returns_sentence_for_start_with_seconds() -> None:
    assert rule_failures(_with(start_time=time(9, 0, 1)), None, []) == [
        FieldMessage("start_time", "Use whole minutes.")
    ]


def returns_sentence_for_end_with_seconds() -> None:
    assert rule_failures(_with(end_time=time(12, 0, 1)), None, []) == [
        FieldMessage("end_time", "Use whole minutes.")
    ]


def returns_sentence_for_end_before_start() -> None:
    assert rule_failures(_with(end_time=time(9, 0)), None, []) == [
        FieldMessage("end_time", "The end must be after the start.")
    ]


def returns_sentence_for_step_outside_5_to_240() -> None:
    assert rule_failures(_with(step=4), None, []) == [
        FieldMessage("slot_step_minutes", "The slot step is 5 to 240 minutes.")
    ]


def returns_sentence_for_room_of_other_department() -> None:
    assert rule_failures(SOUND, RoomChoice(False, True), []) == [
        FieldMessage("room", "Choose an active room of your department.")
    ]


def returns_sentence_for_overlap() -> None:
    assert rule_failures(SOUND, None, [_with(start_time=time(11, 0))]) == [
        FieldMessage("start_time", "Another rule of that day covers these times.")
    ]


def returns_sentences_for_time_off_failures() -> None:
    period = (NOON, NOON + timedelta(hours=1))

    assert time_off_failures(NOON, NOON, "", []) == [
        FieldMessage("ends_at", "The end must be after the start.")
    ]
    assert time_off_failures(*period, "x" * 201, []) == [
        FieldMessage("reason", "The reason is at most 200 characters.")
    ]
    assert time_off_failures(*period, "", [period]) == [
        FieldMessage("starts_at", "This period is already recorded.")
    ]


def returns_visit_at_this_instant_as_last_and_not_next() -> None:
    assert last_and_next_visit(NOON, [NOON]) == (NOON, None)
