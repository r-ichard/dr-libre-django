"""Section 5.6: what a clinician may do with an appointment in each status."""

import pytest

from scheduling.domain.vocabulary import AppointmentStatus


@pytest.mark.parametrize("status", [AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED])
def returns_check_in_no_show_cancel_reschedule_when_not_yet_arrived(
    status: AppointmentStatus,
) -> None:
    from scheduling.domain.staff_actions import StaffAction, staff_actions_for

    assert staff_actions_for(status) == (
        StaffAction.CHECK_IN,
        StaffAction.NO_SHOW,
        StaffAction.CANCEL,
        StaffAction.RESCHEDULE,
    )


def returns_only_complete_and_cancel_when_checked_in() -> None:
    from scheduling.domain.staff_actions import StaffAction, staff_actions_for

    assert staff_actions_for(AppointmentStatus.CHECKED_IN) == (
        StaffAction.COMPLETE,
        StaffAction.CANCEL,
    )


@pytest.mark.parametrize(
    "status",
    [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
)
def returns_nothing_when_appointment_is_finished(status: AppointmentStatus) -> None:
    from scheduling.domain.staff_actions import staff_actions_for

    assert staff_actions_for(status) == ()
