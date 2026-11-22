"""Section 5.8: joining the waitlist, offering a freed slot (on cancel or by an admin) and
accepting an offer. Every change locks the entry, audits and notifies in one transaction."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import islice
from uuid import UUID

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import AppointmentStatus, Role, WaitlistStatus
from scheduling.domain.waitlist_rules import (
    FreedSlot,
    WaitingEntry,
    authorize_join,
    best_match,
)
from scheduling.models import (
    Appointment,
    AppointmentType,
    ClinicianProfile,
    TimeOff,
    User,
    WaitlistEntry,
)
from scheduling.models.booking import NotificationKind
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.notifications import (
    OFFERED_TITLE,
    WAITLIST_BOOKED_TITLE,
    notify_waitlist_patient,
)
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.placement_checks import find_conflicts, slot_of
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
        appointment_type = active_appointment_type(command.appointment_type_id, online_only=False)
        patient_is_active = User.objects.filter(
            pk=patient_id.value, is_active=True, role=Role.PATIENT
        ).exists()
        if appointment_type is None or not patient_is_active:
            return Failure.not_found()
        clinician_id = command.preferred_clinician_id
        if clinician_id is not None and not clinician_offers_type(appointment_type, clinician_id):
            return Failure.not_found()
        problem = window_failure(
            command.earliest_at, command.latest_at, current_request_context().now
        )
        if problem is not None:
            return problem
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
        if isinstance(freed, Failure):
            return freed
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


def clinician_offers_type(appointment_type: AppointmentType, clinician_id: UUID) -> bool:
    return ClinicianProfile.objects.filter(
        pk=clinician_id, department_id=appointment_type.department_id, user__is_active=True
    ).exists()


def window_failure(earliest_at: datetime, latest_at: datetime, now: datetime) -> Failure | None:
    if earliest_at >= latest_at:
        message = "The latest time must be after the earliest time."
        return Failure.invalid_input([FieldMessage("latest_at", message)])
    if latest_at <= now:
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


MAX_SLOTS_CHECKED = 100
RESOURCE_ORDER = ("clinician", "patient", "room")


def _first_free_cancelled_slot(entry: WaitlistEntry) -> Appointment | Failure:
    """The first cancelled slot, soonest first, whose clinician, room and patient are free.

    Busy times are left out in the query, so a fitting time behind any number of busy ones is
    found. Only when nothing fits does a capped scan of all times name what is busy."""
    now = current_request_context().now
    held = _held_slot_ids(entry)
    candidates = _cancelled_candidates(entry, now)
    free = _without_conflicts(candidates, entry.patient_id)
    found = _scan(entry, free.iterator(), held, now)
    if isinstance(found, Appointment):
        return found
    return _scan(entry, islice(candidates.iterator(), MAX_SLOTS_CHECKED), held, now)


def _without_conflicts(
    candidates: QuerySet[Appointment], patient_id: UUID
) -> QuerySet[Appointment]:
    """Same test as `find_conflicts`, one SQL predicate: an active appointment overlapping the
    time that shares its clinician, the patient or its room, or time off of the clinician."""
    overlapping = Appointment.objects.filter(
        status__in=ACTIVE_STATUSES,
        starts_at__lt=OuterRef("ends_at"),
        ends_at__gt=OuterRef("starts_at"),
    ).filter(
        Q(clinician_id=OuterRef("clinician_id"))
        | Q(patient_id=patient_id)
        | Q(room_id=OuterRef("room_id"))
    )
    off = TimeOff.objects.filter(
        clinician_id=OuterRef("clinician_id"),
        starts_at__lt=OuterRef("ends_at"),
        ends_at__gt=OuterRef("starts_at"),
    )
    return candidates.filter(~Exists(overlapping), ~Exists(off))


def _scan(
    entry: WaitlistEntry, candidates: Iterable[Appointment], held: set[UUID], now: datetime
) -> Appointment | Failure:
    seen = 0
    busy: set[str] = set()
    for cancelled in candidates:
        seen += 1
        if cancelled.pk in held:
            continue
        slot = slot_of(entry.appointment_type, cancelled.starts_at, now)
        conflicts = find_conflicts(
            cancelled.clinician_id, entry.patient_id, cancelled.room_id, slot.window, cancelled.pk
        )
        if not conflicts and cancelled.clinician_id not in free_clinician_ids(
            [cancelled.clinician], slot, None
        ):
            conflicts = ["clinician"]
        if not conflicts:
            return cancelled
        busy.update(conflicts)
    if seen == 0 or busy == {"clinician"}:
        return Failure.no_clinician_available()
    return Failure.conflict([name for name in RESOURCE_ORDER if name in busy] or ["offer"])


def _cancelled_candidates(entry: WaitlistEntry, now: datetime) -> QuerySet[Appointment]:
    candidates = Appointment.objects.filter(
        status=AppointmentStatus.CANCELLED,
        appointment_type_id=entry.appointment_type_id,
        starts_at__gt=now,
        starts_at__gte=entry.earliest_at,
        ends_at__lte=entry.latest_at,
    )
    if entry.preferred_clinician_id is not None:
        candidates = candidates.filter(clinician_id=entry.preferred_clinician_id)
    return candidates.select_related("clinician").order_by("starts_at", "pk")


def _held_slot_ids(entry: WaitlistEntry) -> set[UUID]:
    """Slots another entry already holds as its open offer, for this type."""
    held = WaitlistEntry.objects.filter(
        status=WaitlistStatus.OFFERED, appointment_type_id=entry.appointment_type_id
    ).values_list("offered_appointment_id", flat=True)
    return {slot_id for slot_id in held if slot_id is not None}


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
