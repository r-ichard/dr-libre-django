"""Section 5.6: the status transition table, who may make each change, and active."""

from scheduling.domain.vocabulary import AppointmentStatus, Role

# The one definition of active; it mirrors what the no-overlap constraint ignores.
INACTIVE_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
)
ACTIVE_STATUSES: frozenset[AppointmentStatus] = frozenset(AppointmentStatus) - INACTIVE_STATUSES
RESCHEDULABLE_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED}
)

ALLOWED_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: frozenset(
        {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        }
    ),
    AppointmentStatus.CONFIRMED: frozenset(
        {AppointmentStatus.CHECKED_IN, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
    ),
    AppointmentStatus.CHECKED_IN: frozenset(
        {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED}
    ),
}

STAFF_ONLY_TARGETS: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.CHECKED_IN, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}
)


def is_active(status: AppointmentStatus) -> bool:
    return status in ACTIVE_STATUSES


def can_transition(current: AppointmentStatus, target: AppointmentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def may_change_status(
    actor_role: Role, is_own_appointment: bool, target: AppointmentStatus
) -> bool:
    if actor_role == Role.ADMIN:
        return True
    if actor_role == Role.CLINICIAN:
        return is_own_appointment
    return is_own_appointment and target not in STAFF_ONLY_TARGETS
