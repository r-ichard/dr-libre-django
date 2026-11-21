"""Section 5.8: joining the waitlist, offering a freed slot (on cancel or by an admin) and
accepting an offer. Every change locks the entry, audits and notifies in one transaction."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Q

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import AppointmentStatus, Role, WaitlistStatus
from scheduling.domain.waitlist_rules import (
    CancelledSlot,
    FreedSlot,
    WaitingEntry,
    authorize_join,
    best_match,
    first_offerable_slot,
)
from scheduling.models import Appointment, AppointmentType, ClinicianProfile, User, WaitlistEntry
from scheduling.models.booking import NotificationKind
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.notifications import (
    OFFERED_TITLE,
    WAITLIST_BOOKED_TITLE,
    notify_waitlist_patient,
)
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.placement_checks import slot_of
from scheduling.use_cases.placement_choice import free_clinician_ids
from scheduling.use_cases.record_access import guard_record
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import active_appointment_type


@dataclass(frozen=True)
class JoinCommand:
    appointment_type_id: UUID
    earliest_at: datetime
    latest_at: datetime
    preferred_clinician_id: UUID | None
    patient_id: UUID | None


def join_waitlist(command: JoinCommand, actor: User) -> Result[WaitlistEntry]:
    patient_id = authorize_join(Role(actor.role), actor.pk, command.patient_id)
    if isinstance(patient_id, Failure):
        return patient_id
    with transaction.atomic():
        appointment_type = active_appointment_type(command.appointment_type_id)
        patient_is_active = User.objects.filter(
            pk=patient_id.value, is_active=True, role=Role.PATIENT
        ).exists()
        if appointment_type is None or not patient_is_active:
            return Failure.not_found()
        clinician_id = command.preferred_clinician_id
        if clinician_id is not None and not _is_active_clinician_of(appointment_type, clinician_id):
            return Failure.not_found()
        window_failure = _window_failure(command, current_request_context().now)
        if window_failure is not None:
            return window_failure
        entry = WaitlistEntry.objects.create(
            patient_id=patient_id.value,
            appointment_type=appointment_type,
            preferred_clinician_id=clinician_id,
            earliest_at=command.earliest_at,
            latest_at=command.latest_at,
            status=WaitlistStatus.WAITING,
        )
        audit_waitlist_change("waitlist.join", entry, actor, [])
        return Success(entry)


def offer_freed_slot(freed: Appointment, actor: User | None) -> None:
    """Called by the cancel in its transaction: the best waiting entry gets the freed slot."""
    waiting = (
        WaitlistEntry.objects.select_for_update(of=("self",))
        .filter(status=WaitlistStatus.WAITING, appointment_type_id=freed.appointment_type_id)
        .filter(Q(preferred_clinician__isnull=True) | Q(preferred_clinician_id=freed.clinician_id))
        .order_by("created_at", "pk")
    )
    entries = {entry.pk: entry for entry in waiting}
    slot = FreedSlot(freed.clinician_id, freed.starts_at, freed.ends_at)
    winner = best_match(
        [_waiting_entry_of(entry) for entry in entries.values()],
        slot,
        current_request_context().now,
    )
    if winner is not None:
        _offer(entries[winner], freed, actor)


def offer_waitlist_entry(entry_id: UUID, actor: User) -> Result[WaitlistEntry]:
    if actor.role != Role.ADMIN:
        return Failure.forbidden()
    with transaction.atomic():
        entry = _lock_entry(entry_id)
        if entry is None:
            return Failure.not_found()
        if entry.status != WaitlistStatus.WAITING:
            return Failure.invalid_transition(entry.status)
        freed = _first_free_cancelled_slot(entry)
        if freed is None:
            return Failure.no_clinician_available()
        _offer(entry, freed, actor)
        return Success(entry)


def accept_offer(entry_id: UUID, actor: User) -> Result[WaitlistEntry]:
    with transaction.atomic():
        locked = guard_record(_lock_entry(entry_id), lambda entry: _may_accept(entry, actor))
        if isinstance(locked, Failure):
            return locked
        entry = locked.value
        if entry.status != WaitlistStatus.OFFERED or entry.offered_appointment is None:
            return Failure.invalid_transition(entry.status)
        offered = entry.offered_appointment
        command = PlacementCommand(
            entry.appointment_type_id,
            offered.starts_at,
            offered.clinician_id,
            entry.patient_id,
            None,
            announce=False,
        )
        placed = place_appointment(command, actor)
        if isinstance(placed, Failure):
            return placed
        entry.status = WaitlistStatus.BOOKED
        entry.save()
        appointment = placed.value
        appointment.waitlist_entry = entry
        appointment.inherited_version = entry.version
        appointment.save()
        audit_waitlist_change("waitlist.accept", entry, actor, ["status"])
        notify_waitlist_patient(
            entry, NotificationKind.WAITLIST_BOOKED, WAITLIST_BOOKED_TITLE, appointment.starts_at
        )
        return Success(entry)


def _may_accept(entry: WaitlistEntry, actor: User) -> bool:
    return actor.role == Role.ADMIN or entry.patient_id == actor.pk


def _is_active_clinician_of(appointment_type: AppointmentType, clinician_id: UUID) -> bool:
    return ClinicianProfile.objects.filter(
        pk=clinician_id, department_id=appointment_type.department_id, user__is_active=True
    ).exists()


def _window_failure(command: JoinCommand, now: datetime) -> Failure | None:
    if command.earliest_at >= command.latest_at:
        message = "The latest time must be after the earliest time."
        return Failure.invalid_input([FieldMessage("latest_at", message)])
    if command.latest_at <= now:
        return Failure.invalid_input([FieldMessage("latest_at", "The latest time has passed.")])
    return None


def _lock_entry(entry_id: UUID) -> WaitlistEntry | None:
    return (
        WaitlistEntry.objects.select_for_update(of=("self",))
        .select_related(
            "appointment_type__department__hospital",
            "offered_appointment__clinician__user",
        )
        .filter(pk=entry_id)
        .first()
    )


def _waiting_entry_of(entry: WaitlistEntry) -> WaitingEntry:
    return WaitingEntry(
        entry.pk,
        entry.created_at,
        entry.preferred_clinician_id,
        entry.earliest_at,
        entry.latest_at,
    )


def _first_free_cancelled_slot(entry: WaitlistEntry) -> Appointment | None:
    now = current_request_context().now
    cancelled = Appointment.objects.filter(
        status=AppointmentStatus.CANCELLED,
        appointment_type_id=entry.appointment_type_id,
        starts_at__gt=now,
    ).select_related("clinician")
    by_id = {appointment.pk: appointment for appointment in cancelled}
    held = set(
        WaitlistEntry.objects.filter(
            status=WaitlistStatus.OFFERED, offered_appointment_id__in=by_id
        ).values_list("offered_appointment_id", flat=True)
    )
    slots = [
        CancelledSlot(row.pk, row.clinician_id, row.starts_at, row.ends_at)
        for row in by_id.values()
    ]
    while (chosen := first_offerable_slot(_waiting_entry_of(entry), slots, held, now)) is not None:
        if _clinician_is_free(entry, by_id[chosen], now):
            return by_id[chosen]
        held.add(chosen)
    return None


def _clinician_is_free(entry: WaitlistEntry, cancelled: Appointment, now: datetime) -> bool:
    slot = slot_of(entry.appointment_type, cancelled.starts_at, now)
    return cancelled.clinician_id in free_clinician_ids([cancelled.clinician], slot, None)


def _offer(entry: WaitlistEntry, freed: Appointment, actor: User | None) -> None:
    entry.status = WaitlistStatus.OFFERED
    entry.offered_appointment = freed
    entry.save()
    audit_waitlist_change("waitlist.offer", entry, actor, ["status", "offered_appointment"])
    notify_waitlist_offer(entry)


def notify_waitlist_offer(entry: WaitlistEntry) -> None:
    offered = entry.offered_appointment
    if offered is None:
        raise ValueError("an offer needs an offered appointment")
    notify_waitlist_patient(
        entry, NotificationKind.WAITLIST_OFFERED, OFFERED_TITLE, offered.starts_at
    )


def audit_waitlist_change(
    action: str, entry: WaitlistEntry, actor: User | None, fields: list[str]
) -> None:
    ids = {"waitlist_entry_id": entry.pk, "patient_id": entry.patient_id}
    metadata = AuditMetadata(
        ids=ids,
        statuses={"waitlist_status": WaitlistStatus(entry.status)},
        changed_fields=changed_field_names(WaitlistEntry, fields),
    )
    record_audit(AuditEvent(action, "WaitlistEntry", str(entry.pk), metadata), actor)
