"""Section 5.6: what a clinician may do with an appointment in each status."""

from enum import StrEnum

from scheduling.domain.appointment_status import RESCHEDULABLE_STATUSES, can_transition
from scheduling.domain.vocabulary import AppointmentStatus


class StaffAction(StrEnum):
    CHECK_IN = "check-in"
    COMPLETE = "complete"
    NO_SHOW = "no-show"
    CANCEL = "cancel"
    RESCHEDULE = "reschedule"


TARGET_OF_ACTION = {
    StaffAction.CHECK_IN: AppointmentStatus.CHECKED_IN,
    StaffAction.COMPLETE: AppointmentStatus.COMPLETED,
    StaffAction.NO_SHOW: AppointmentStatus.NO_SHOW,
    StaffAction.CANCEL: AppointmentStatus.CANCELLED,
}


def staff_actions_for(status: AppointmentStatus) -> tuple[StaffAction, ...]:
    allowed = [
        action for action, target in TARGET_OF_ACTION.items() if can_transition(status, target)
    ]
    if status in RESCHEDULABLE_STATUSES:
        allowed.append(StaffAction.RESCHEDULE)
    return tuple(allowed)
