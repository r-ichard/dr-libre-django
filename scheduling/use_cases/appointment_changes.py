"""Section 5.6: cancel, reschedule and the status actions. Each change locks the appointment,
checks the record rule and the status table, writes, audits and notifies in one transaction."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from django.db import transaction

from scheduling.domain.appointment_status import (
    RESCHEDULABLE_STATUSES,
    can_transition,
    may_change_status,
)
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.booking_rules import BookingAction, BookingAttempt, violated_rules
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.vocabulary import AppointmentStatus, Role
from scheduling.models import Appointment, User
from scheduling.models.booking import NotificationKind
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.notifications import CANCELLED_TITLE, RESCHEDULED_TITLE, notify_patient
from scheduling.use_cases.placement import replace_placement
from scheduling.use_cases.record_access import guard_record
from scheduling.use_cases.request_context import current_request_context

STATUS_ACTION_NAMES = {
    AppointmentStatus.CHECKED_IN: "appointment.check_in",
    AppointmentStatus.COMPLETED: "appointment.complete",
    AppointmentStatus.NO_SHOW: "appointment.no_show",
}


def cancel_appointment(appointment_id: UUID, reason: str, actor: User) -> Result[Appointment]:
    with transaction.atomic():
        locked = _lock_for_change(appointment_id, actor, AppointmentStatus.CANCELLED)
        if isinstance(locked, Failure):
            return locked
        appointment = locked.value
        if not can_transition(AppointmentStatus(appointment.status), AppointmentStatus.CANCELLED):
            return Failure.invalid_transition(appointment.status)
        now = current_request_context().now
        violations = _cancellation_violations(appointment, actor, now)
        if violations:
            return Failure.rule_violation(violations)
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = now
        appointment.cancellation_reason = reason
        appointment.save()
        _audit(
            "appointment.cancel",
            appointment,
            actor,
            ["status", "cancelled_at", "cancellation_reason"],
        )
        notify_patient(appointment, NotificationKind.APPOINTMENT_CANCELLED, CANCELLED_TITLE)
        return Success(appointment)


def reschedule_appointment(
    appointment_id: UUID, starts_at: datetime, actor: User
) -> Result[Appointment]:
    with transaction.atomic():
        locked = _lock_for_change(appointment_id, actor, AppointmentStatus.BOOKED)
        if isinstance(locked, Failure):
            return locked
        appointment = locked.value
        if AppointmentStatus(appointment.status) not in RESCHEDULABLE_STATUSES:
            return Failure.invalid_transition(appointment.status)
        moved = replace_placement(appointment, starts_at, actor)
        if isinstance(moved, Failure):
            return moved
        _audit("appointment.reschedule", appointment, actor, ["starts_at", "ends_at", "room"])
        notify_patient(appointment, NotificationKind.SCHEDULE_CHANGED, RESCHEDULED_TITLE)
        return moved


def change_status(
    appointment_id: UUID, target: AppointmentStatus, actor: User
) -> Result[Appointment]:
    with transaction.atomic():
        locked = _lock_for_change(appointment_id, actor, target)
        if isinstance(locked, Failure):
            return locked
        appointment = locked.value
        if not can_transition(AppointmentStatus(appointment.status), target):
            return Failure.invalid_transition(appointment.status)
        appointment.status = target
        appointment.save()
        _audit(STATUS_ACTION_NAMES[target], appointment, actor, ["status"])
        return Success(appointment)


def _lock_for_change(
    appointment_id: UUID, actor: User, target: AppointmentStatus
) -> Result[Appointment]:
    appointment = (
        Appointment.objects.select_for_update(of=("self",))
        .select_related(
            "appointment_type__department__hospital", "clinician__user", "patient", "room"
        )
        .filter(pk=appointment_id)
        .first()
    )
    return guard_record(appointment, _may_change(actor, target))


def _may_change(actor: User, target: AppointmentStatus) -> Callable[[Appointment], bool]:
    def allowed(appointment: Appointment) -> bool:
        own = (
            appointment.clinician.user_id == actor.pk
            if actor.role == Role.CLINICIAN
            else appointment.patient_id == actor.pk
        )
        return may_change_status(Role(actor.role), own, target)

    return allowed


def _cancellation_violations(appointment: Appointment, actor: User, now: datetime) -> list[str]:
    attempt = BookingAttempt(
        BookingAction.CANCEL, Role(actor.role), now, None, appointment.starts_at, 0, True, True
    )
    return [rule.value for rule in violated_rules(attempt)]


def _audit(action: str, appointment: Appointment, actor: User, fields: list[str]) -> None:
    metadata = AuditMetadata(
        ids={
            "appointment_id": appointment.pk,
            "patient_id": appointment.patient_id,
            "clinician_id": appointment.clinician_id,
        },
        statuses={"appointment_status": AppointmentStatus(appointment.status)},
        changed_fields=changed_field_names(Appointment, fields),
    )
    record_audit(AuditEvent(action, "Appointment", str(appointment.pk), metadata), actor)
