"""Section 5.6: the status transition table, who may make each change, and active."""

from itertools import product

import pytest

from scheduling.domain.appointment_status import (
    ACTIVE_STATUSES,
    RESCHEDULABLE_STATUSES,
    can_transition,
    is_active,
    may_change_status,
)
from scheduling.models.booking import AppointmentStatus
from scheduling.models.people import Role

TABLE = {
    AppointmentStatus.BOOKED: (
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ),
    AppointmentStatus.CONFIRMED: (
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ),
    AppointmentStatus.CHECKED_IN: (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED),
}
ALLOWED_PAIRS = [(source, target) for source, targets in TABLE.items() for target in targets]
FORBIDDEN_PAIRS = [
    pair for pair in product(AppointmentStatus, repeat=2) if pair not in ALLOWED_PAIRS
]


def returns_false_when_status_is_cancelled_or_no_show() -> None:
    assert not is_active(AppointmentStatus.CANCELLED)
    assert not is_active(AppointmentStatus.NO_SHOW)


def returns_true_when_status_is_one_of_the_four_active_ones() -> None:
    active = {status for status in AppointmentStatus if is_active(status)}
    assert active == {
        AppointmentStatus.BOOKED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
        AppointmentStatus.COMPLETED,
    }
    assert set(ACTIVE_STATUSES) == active


@pytest.mark.parametrize(("source", "target"), ALLOWED_PAIRS)
def returns_true_when_transition_is_in_the_table(
    source: AppointmentStatus, target: AppointmentStatus
) -> None:
    assert can_transition(source, target) is True


@pytest.mark.parametrize(("source", "target"), FORBIDDEN_PAIRS)
def returns_false_when_transition_is_not_in_table(
    source: AppointmentStatus, target: AppointmentStatus
) -> None:
    assert can_transition(source, target) is False


def returns_true_only_for_booked_and_confirmed_when_asked_if_reschedulable() -> None:
    assert set(RESCHEDULABLE_STATUSES) == {AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED}


def returns_false_when_patient_checks_in() -> None:
    assert not may_change_status(Role.PATIENT, True, AppointmentStatus.CHECKED_IN)


def returns_true_when_clinician_completes_own_appointment() -> None:
    assert may_change_status(Role.CLINICIAN, True, AppointmentStatus.COMPLETED)


def returns_false_when_clinician_completes_other_clinicians_appointment() -> None:
    assert not may_change_status(Role.CLINICIAN, False, AppointmentStatus.COMPLETED)


def returns_true_when_admin_marks_no_show_on_any_appointment() -> None:
    assert may_change_status(Role.ADMIN, False, AppointmentStatus.NO_SHOW)


def returns_true_when_patient_cancels_own_appointment() -> None:
    assert may_change_status(Role.PATIENT, True, AppointmentStatus.CANCELLED)


def returns_false_when_patient_cancels_other_appointment() -> None:
    assert not may_change_status(Role.PATIENT, False, AppointmentStatus.CANCELLED)


def returns_true_when_clinician_cancels_own_appointment() -> None:
    assert may_change_status(Role.CLINICIAN, True, AppointmentStatus.CANCELLED)


def returns_false_when_clinician_cancels_other_clinicians_appointment() -> None:
    assert not may_change_status(Role.CLINICIAN, False, AppointmentStatus.CANCELLED)


def returns_true_when_admin_cancels_any_appointment() -> None:
    assert may_change_status(Role.ADMIN, False, AppointmentStatus.CANCELLED)


@pytest.mark.parametrize(
    "target",
    [AppointmentStatus.CHECKED_IN, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW],
)
def returns_false_when_patient_makes_a_staff_only_change_on_own_appointment(
    target: AppointmentStatus,
) -> None:
    assert may_change_status(Role.PATIENT, True, target) is False
