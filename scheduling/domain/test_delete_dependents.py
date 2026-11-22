"""Task 18, section 10: what blocks deleting a record, as a pure decision over counts."""

import pytest


def _refusal(kind: str, counts: dict[str, int]) -> tuple[object, ...]:
    from scheduling.domain.delete_dependents import delete_refusal as decide

    return tuple(decide(kind, counts))


def _dependent(reason: str, count: int) -> object:  # noqa: N802 - reads as the value it builds
    from scheduling.domain.delete_dependents import Dependent as Reason

    return Reason(reason, count)


ALL_KINDS_EMPTY = {
    "hospital": {"departments": 0},
    "department": {"clinicians": 0, "rooms": 0, "appointment_types": 0},
    "specialty": {"clinicians": 0},
    "room": {"appointments": 0, "availability_rules": 0, "default_room_clinicians": 0},
    "appointment_type": {"appointments": 0, "waitlist_entries": 0},
}


@pytest.mark.parametrize("kind", sorted(ALL_KINDS_EMPTY))
def returns_no_refusal_when_nothing_depends_on_the_record(kind: str) -> None:
    assert _refusal(kind, ALL_KINDS_EMPTY[kind]) == ()


def returns_departments_count_when_hospital_has_three_departments() -> None:
    assert _refusal("hospital", {"departments": 3}) == (_dependent("departments", 3),)


def returns_one_when_hospital_has_a_single_department() -> None:
    assert _refusal("hospital", {"departments": 1}) == (_dependent("departments", 1),)


def returns_clinicians_count_when_specialty_is_held_by_two_clinicians() -> None:
    assert _refusal("specialty", {"clinicians": 2}) == (_dependent("clinicians", 2),)


def returns_every_reason_with_its_count_when_department_has_clinicians_rooms_and_types() -> None:
    counts = {"clinicians": 4, "rooms": 2, "appointment_types": 1}

    refusal = _refusal("department", counts)

    assert refusal == (
        _dependent("clinicians", 4),
        _dependent("rooms", 2),
        _dependent("appointment_types", 1),
    )


def returns_only_the_reasons_that_count_when_department_has_only_rooms() -> None:
    counts = {"clinicians": 0, "rooms": 2, "appointment_types": 0}

    assert _refusal("department", counts) == (_dependent("rooms", 2),)


def returns_appointments_rules_and_default_clinicians_when_room_has_all_three() -> None:
    counts = {"appointments": 5, "availability_rules": 3, "default_room_clinicians": 2}

    refusal = _refusal("room", counts)

    assert refusal == (
        _dependent("appointments", 5),
        _dependent("availability_rules", 3),
        _dependent("default_room_clinicians", 2),
    )


def returns_only_default_clinicians_when_room_is_only_a_default_room() -> None:
    counts = {"appointments": 0, "availability_rules": 0, "default_room_clinicians": 1}

    assert _refusal("room", counts) == (_dependent("default_room_clinicians", 1),)


def returns_appointments_and_waitlist_entries_when_type_has_both() -> None:
    counts = {"appointments": 7, "waitlist_entries": 1}

    refusal = _refusal("appointment_type", counts)

    assert refusal == (_dependent("appointments", 7), _dependent("waitlist_entries", 1))


def returns_only_waitlist_entries_when_type_has_no_appointments() -> None:
    counts = {"appointments": 0, "waitlist_entries": 2}

    assert _refusal("appointment_type", counts) == (_dependent("waitlist_entries", 2),)


def returns_no_refusal_when_a_count_is_not_in_the_section_10_table_for_the_kind() -> None:
    assert _refusal("hospital", {"departments": 0, "rooms": 9}) == ()


def raises_when_the_kind_is_not_one_of_the_five_records() -> None:
    with pytest.raises(KeyError):
        _refusal("clinician_profile", {"appointments": 1})
