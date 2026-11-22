"""Task 19, sections 3.2 and 10: the clinician profile rules that need no stored data."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import time

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

TITLE_MAXIMUM = 50
NO_AVAILABILITY = "No weekly availability"
# Weekday 0 is Sunday, as stored; the week shown starts on Monday.
WEEKDAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 0: "Sun"}
WEEK_ORDER = (1, 2, 3, 4, 5, 6, 0)


@dataclass(frozen=True)
class WeeklyHours:
    weekday: int
    start_time: time
    end_time: time


def check_title(raw: str) -> Result[str]:
    title = raw.strip()
    if not title:
        return Failure.invalid_input([FieldMessage("title", "Enter a title.")])
    if len(title) > TITLE_MAXIMUM:
        message = f"Use at most {TITLE_MAXIMUM} characters."
        return Failure.invalid_input([FieldMessage("title", message)])
    return Success(title)


def check_weight(raw: str) -> Result[int]:
    text = raw.strip()
    if text.isascii() and text.isdigit() and int(text) >= 1:
        return Success(int(text))
    message = "Use a whole number of 1 or more."
    return Failure.invalid_input([FieldMessage("round_robin_weight", message)])


def department_move_refusals(*, moves: bool, counts: Mapping[str, int]) -> list[str]:
    if not moves:
        return []
    refusals = []
    appointments = counts["upcoming_appointments"]
    if appointments:
        noun = "appointment is" if appointments == 1 else "appointments are"
        refusals.append(f"{appointments} upcoming {noun} booked with this clinician.")
    rules = counts["availability_rules"]
    if rules:
        noun = "rule belongs" if rules == 1 else "rules belong"
        refusals.append(f"{rules} availability {noun} to this department.")
    if counts["default_room"]:
        refusals.append("A default room of this department is set.")
    return refusals


def availability_summary(rules: Sequence[WeeklyHours]) -> str:
    """Weekdays sharing the same hours are grouped; groups follow the hours."""
    if not rules:
        return NO_AVAILABILITY
    hours = sorted({(rule.start_time, rule.end_time) for rule in rules})
    return "; ".join(
        f"{_weekday_list(rules, start, end)} {start:%H:%M}–{end:%H:%M}" for start, end in hours
    )


def _weekday_list(rules: Sequence[WeeklyHours], start: time, end: time) -> str:
    days = {rule.weekday for rule in rules if (rule.start_time, rule.end_time) == (start, end)}
    return ", ".join(WEEKDAY_NAMES[day] for day in WEEK_ORDER if day in days)
