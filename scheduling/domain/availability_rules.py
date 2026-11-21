"""Section 9.3: when an availability rule is valid. Weekdays run 0 Sunday to 6 Saturday."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time

from scheduling.domain.failure import FieldMessage

WEEKDAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)
SLOT_STEP_MINIMUM = 5
SLOT_STEP_MAXIMUM = 240


@dataclass(frozen=True)
class RuleTimes:
    weekday: int
    start_time: time
    end_time: time
    step: int


@dataclass(frozen=True)
class RoomChoice:
    exists_in_department: bool
    is_active: bool


def weekday_name(weekday: int) -> str:
    return WEEKDAY_NAMES[weekday]


def new_rule_validity(today: date) -> tuple[date, None]:
    return today, None


def rule_failures(
    rule: RuleTimes, room: RoomChoice | None, others: Sequence[RuleTimes]
) -> list[FieldMessage]:
    failures = _weekday_failures(rule) + _time_failures(rule) + _room_failures(room)
    if not failures:
        failures = _overlap_failures(rule, others)
    return failures


def _weekday_failures(rule: RuleTimes) -> list[FieldMessage]:
    if 0 <= rule.weekday < len(WEEKDAY_NAMES):
        return []
    return [FieldMessage("weekday", "Choose a day of the week.")]


def _time_failures(rule: RuleTimes) -> list[FieldMessage]:
    failures: list[FieldMessage] = []
    if not _is_whole_minute(rule.start_time):
        failures.append(FieldMessage("start_time", "Use whole minutes."))
    if not _is_whole_minute(rule.end_time):
        failures.append(FieldMessage("end_time", "Use whole minutes."))
    elif rule.end_time <= rule.start_time:
        failures.append(FieldMessage("end_time", "The end must be after the start."))
    if not SLOT_STEP_MINIMUM <= rule.step <= SLOT_STEP_MAXIMUM:
        failures.append(
            FieldMessage(
                "slot_step_minutes",
                f"The slot step is {SLOT_STEP_MINIMUM} to {SLOT_STEP_MAXIMUM} minutes.",
            )
        )
    return failures


def _is_whole_minute(moment: time) -> bool:
    return moment.second == 0 and moment.microsecond == 0


def _room_failures(room: RoomChoice | None) -> list[FieldMessage]:
    if room is None or (room.exists_in_department and room.is_active):
        return []
    return [FieldMessage("room", "Choose an active room of your department.")]


def _overlap_failures(rule: RuleTimes, others: Sequence[RuleTimes]) -> list[FieldMessage]:
    """Half-open intervals: a rule ending at 12:00 and one starting at 12:00 only touch."""
    for other in others:
        if (
            other.weekday == rule.weekday
            and other.start_time < rule.end_time
            and rule.start_time < other.end_time
        ):
            return [FieldMessage("start_time", "Another rule of that day covers these times.")]
    return []
