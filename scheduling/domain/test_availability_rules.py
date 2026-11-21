"""Section 9.3: an availability rule is valid when times, step, room and neighbours allow it."""

from datetime import date, time

import pytest

from scheduling.domain.failure import FieldMessage

SUNDAY, MONDAY, SATURDAY = 0, 1, 6
ACTIVE_ROOM_OF_DEPARTMENT = (True, True)


def _failures(
    weekday: int = MONDAY,
    start: time = time(9, 0),
    end: time = time(12, 0),
    step: int = 15,
    room: tuple[bool, bool] | None = None,
    others: tuple[tuple[int, time, time], ...] = (),
) -> list[FieldMessage]:
    from scheduling.domain.availability_rules import RoomChoice, RuleTimes, rule_failures

    choice = None if room is None else RoomChoice(room[0], room[1])
    return rule_failures(
        RuleTimes(weekday, start, end, step), choice, [RuleTimes(*o, step=15) for o in others]
    )


def _names(failures: list[FieldMessage]) -> list[str]:
    return [item.field for item in failures]


def returns_no_failure_when_rule_is_sound() -> None:
    assert _failures(room=ACTIVE_ROOM_OF_DEPARTMENT) == []


@pytest.mark.parametrize(("start", "end"), [(time(12, 0), time(12, 0)), (time(12, 0), time(9, 0))])
def rejects_rule_when_ends_at_or_before_start(start: time, end: time) -> None:
    assert _names(_failures(start=start, end=end)) == ["end_time"]


def rejects_rule_when_time_has_seconds() -> None:
    assert _names(_failures(start=time(9, 0, 30))) == ["start_time"]


@pytest.mark.parametrize("step", [4, 241])
def rejects_rule_when_step_is_4_or_241(step: int) -> None:
    assert _names(_failures(step=step)) == ["slot_step_minutes"]


@pytest.mark.parametrize("step", [5, 240])
def returns_accepts_rule_when_step_is_5_or_240(step: int) -> None:
    assert _failures(step=step) == []


@pytest.mark.parametrize("weekday", [-1, 7])
def rejects_rule_when_weekday_outside_0_to_6(weekday: int) -> None:
    assert _names(_failures(weekday=weekday)) == ["weekday"]


@pytest.mark.parametrize("weekday", [SUNDAY, SATURDAY])
def returns_accepts_rule_when_weekday_is_0_or_6(weekday: int) -> None:
    assert _failures(weekday=weekday) == []


def rejects_rule_when_room_inactive() -> None:
    assert _names(_failures(room=(True, False))) == ["room"]


def rejects_rule_when_room_of_other_department() -> None:
    assert _names(_failures(room=(False, True))) == ["room"]


def returns_accepts_rule_when_touching_other_rule() -> None:
    others = ((MONDAY, time(12, 0), time(15, 0)), (MONDAY, time(6, 0), time(9, 0)))

    assert _failures(others=others) == []


def rejects_rule_when_overlapping_other_by_one_minute() -> None:
    assert _names(_failures(others=((MONDAY, time(11, 59), time(15, 0)),))) == ["start_time"]


def rejects_rule_when_inside_other_rule() -> None:
    assert _names(_failures(others=((MONDAY, time(8, 0), time(13, 0)),))) == ["start_time"]


def returns_accepts_rule_when_same_times_other_weekday() -> None:
    assert _failures(others=((SATURDAY, time(9, 0), time(12, 0)),)) == []


def returns_names_weekday_sunday_when_0_and_saturday_when_6() -> None:
    from scheduling.domain.availability_rules import WEEKDAY_NAMES, weekday_name

    assert (weekday_name(0), weekday_name(1), weekday_name(6)) == ("Sunday", "Monday", "Saturday")
    assert len(WEEKDAY_NAMES) == 7


def returns_starts_new_rule_today_with_no_end() -> None:
    from scheduling.domain.availability_rules import new_rule_validity

    assert new_rule_validity(date(2030, 1, 7)) == (date(2030, 1, 7), None)
