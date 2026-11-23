"""Sections 3.2 and 10: the clinician profile rules that need no stored data."""

from datetime import time

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success


def returns_the_title_trimmed_when_it_has_50_characters() -> None:
    from scheduling.domain.clinician_rules import check_title

    assert check_title(" " + "t" * 50 + " ") == Success("t" * 50)


def returns_message_on_title_field_when_title_has_51_characters() -> None:
    from scheduling.domain.clinician_rules import check_title

    assert check_title("t" * 51) == Failure.invalid_input(
        [FieldMessage("title", "Use at most 50 characters.")]
    )


def returns_message_on_title_field_when_title_is_blank() -> None:
    from scheduling.domain.clinician_rules import check_title

    assert check_title("  ") == Failure.invalid_input([FieldMessage("title", "Enter a title.")])


@pytest.mark.parametrize(("raw", "weight"), [("1", 1), (" 2 ", 2), ("32767", 32767)])
def returns_the_weight_when_it_is_a_whole_number_of_1_or_more(raw: str, weight: int) -> None:
    from scheduling.domain.clinician_rules import check_weight

    assert check_weight(raw) == Success(weight)


@pytest.mark.parametrize("raw", ["0", "-1", "1.5", "", "abc"])
def returns_message_on_weight_field_when_it_is_not_a_whole_number_of_1_or_more(raw: str) -> None:
    from scheduling.domain.clinician_rules import check_weight

    assert check_weight(raw) == Failure.invalid_input(
        [FieldMessage("round_robin_weight", "Use a whole number of 1 or more.")]
    )


def returns_no_refusal_when_department_stays_the_same_whatever_the_counts() -> None:
    from scheduling.domain.clinician_rules import department_move_refusals

    counts = {"upcoming_appointments": 4, "availability_rules": 2, "default_room": 1}

    assert department_move_refusals(moves=False, counts=counts) == []


def returns_no_refusal_when_clinician_with_nothing_attached_moves() -> None:
    from scheduling.domain.clinician_rules import department_move_refusals

    counts = {"upcoming_appointments": 0, "availability_rules": 0, "default_room": 0}

    assert department_move_refusals(moves=True, counts=counts) == []


def returns_three_reasons_when_department_changes_with_appointments_rules_and_default_room() -> (
    None
):
    from scheduling.domain.clinician_rules import department_move_refusals

    counts = {"upcoming_appointments": 2, "availability_rules": 3, "default_room": 1}

    assert department_move_refusals(moves=True, counts=counts) == [
        "2 upcoming appointments are booked with this clinician.",
        "3 availability rules belong to this department.",
        "A default room of this department is set.",
    ]


def returns_only_the_reasons_that_count_when_department_changes_with_one_rule() -> None:
    from scheduling.domain.clinician_rules import department_move_refusals

    counts = {"upcoming_appointments": 0, "availability_rules": 1, "default_room": 0}

    assert department_move_refusals(moves=True, counts=counts) == [
        "1 availability rule belongs to this department."
    ]


def returns_the_weekday_group_with_its_hours_when_monday_and_wednesday_share_hours() -> None:
    from scheduling.domain.clinician_rules import WeeklyHours, availability_summary

    rules = [
        WeeklyHours(3, time(9, 0), time(12, 0)),
        WeeklyHours(1, time(9, 0), time(12, 0)),
    ]

    assert availability_summary(rules) == "Mon, Wed 09:00–12:00"


def returns_one_group_per_hours_in_weekday_order_when_hours_differ() -> None:
    from scheduling.domain.clinician_rules import WeeklyHours, availability_summary

    rules = [
        WeeklyHours(2, time(13, 0), time(17, 0)),
        WeeklyHours(1, time(9, 0), time(12, 0)),
        WeeklyHours(2, time(9, 0), time(12, 0)),
    ]

    assert availability_summary(rules) == "Mon, Tue 09:00–12:00; Tue 13:00–17:00"


def returns_sunday_last_when_the_week_includes_sunday_and_monday() -> None:
    from scheduling.domain.clinician_rules import WeeklyHours, availability_summary

    rules = [WeeklyHours(0, time(8, 0), time(9, 0)), WeeklyHours(1, time(8, 0), time(9, 0))]

    assert availability_summary(rules) == "Mon, Sun 08:00–09:00"


def returns_text_saying_none_when_the_clinician_has_no_weekly_availability() -> None:
    from scheduling.domain.clinician_rules import availability_summary

    assert availability_summary([]) == "No weekly availability"


def returns_singular_appointment_sentence_when_one_upcoming_appointment_blocks_the_move() -> None:
    from scheduling.domain.clinician_rules import department_move_refusals

    counts = {"upcoming_appointments": 1, "availability_rules": 0, "default_room": 0}

    refusals = department_move_refusals(moves=True, counts=counts)

    assert refusals == ["1 upcoming appointment is booked with this clinician."]


def returns_message_on_title_field_when_title_holds_a_line_break() -> None:
    from scheduling.domain.clinician_rules import check_title

    assert check_title("Dr\nX") == Failure.invalid_input(
        [FieldMessage("title", 'This field takes one line. Remove the line break after "Dr".')]
    )
