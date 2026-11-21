"""Sections 5.2, 5.4, 5.5: the one use case every booking path calls to place an appointment.

Lock order, global against deadlock: clinicians by id, patient, rooms by id. Checks run after
all locks; the exclusion constraints stay the last line."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.first_available import Candidate, first_available
from scheduling.domain.placement_rules import (
    BookingActor,
    BookingParties,
    NamedParties,
    authorize_booking,
    booked_notification_text,
    choose_room,
)
from scheduling.domain.slot_search import QueryTooWide, free_slots_by_start
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, Role
from scheduling.models import (
    Appointment,
    AppointmentType,
    ClinicianProfile,
    Notification,
    Room,
    User,
)
from scheduling.models.booking import NotificationKind
from scheduling.use_cases import placement_checks
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.placement_checks import PlacementSlot, slot_of
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import (
    active_appointment_type,
    department_clinicians,
    load_schedules,
)

BOOKED_TITLE = "Appointment booked"


@dataclass(frozen=True)
class PlacementCommand:
    appointment_type_id: UUID
    starts_at: datetime
    clinician_id: UUID | None
    patient_id: UUID | None
    room_id: UUID | None


def place_appointment(command: PlacementCommand, actor: User) -> Result[Appointment]:
    named = NamedParties(command.patient_id, command.clinician_id, command.room_id)
    authorized = authorize_booking(_booking_actor(actor), named)
    if isinstance(authorized, Failure):
        return authorized
    with transaction.atomic():
        return _place(command, actor, authorized.value)


def _booking_actor(actor: User) -> BookingActor:
    role = Role(actor.role)
    clinician_id = None
    if role == Role.CLINICIAN:
        profiles = ClinicianProfile.objects.filter(user_id=actor.pk)
        clinician_id = profiles.values_list("pk", flat=True).first()
    return BookingActor(role, actor.pk, clinician_id)


def _place(command: PlacementCommand, actor: User, parties: BookingParties) -> Result[Appointment]:
    appointment_type = active_appointment_type(command.appointment_type_id)
    if appointment_type is None:
        return Failure.not_found()
    pool = _lock_clinicians(appointment_type, parties.clinician_id)
    patient = _lock_patient(parties.patient_id)
    rooms = _lock_rooms(appointment_type, parties.room_id)
    named_clinician_missing = parties.clinician_id is not None and not pool
    if named_clinician_missing or patient is None or rooms is None:
        return Failure.not_found()
    now = current_request_context().now
    slot = slot_of(appointment_type, command.starts_at, now)
    free_ids = _free_clinician_ids(pool, slot)
    chosen = _choose_clinician(pool, free_ids, parties, slot)
    if isinstance(chosen, Failure):
        return chosen
    refused = _first_refusal(chosen, patient, parties, slot, chosen.pk in free_ids, actor)
    if refused is not None:
        return refused
    room_id = _choose_room(chosen, rooms, parties, slot)
    if isinstance(room_id, Failure):
        return room_id
    return _book(chosen, patient, room_id.value, parties, slot, actor)


def _lock_clinicians(
    appointment_type: AppointmentType, clinician_id: UUID | None
) -> list[ClinicianProfile]:
    candidates = department_clinicians(appointment_type, clinician_id)
    # of=self: the user rows stay unlocked, or the lock order would no longer be ours.
    locked = candidates.select_for_update(of=("self",), no_key=True).order_by("pk")
    return list(locked)


def _lock_patient(patient_id: UUID) -> User | None:
    patients = User.objects.select_for_update(no_key=True)
    return patients.filter(pk=patient_id, is_active=True, role=Role.PATIENT).first()


def _lock_rooms(appointment_type: AppointmentType, room_id: UUID | None) -> list[Room] | None:
    """None when the named room is not an active room of the department; an empty list when the
    type needs no room."""
    active = Room.objects.filter(department_id=appointment_type.department_id, is_active=True)
    if room_id is not None:
        active = active.filter(pk=room_id)
    elif not appointment_type.needs_room:
        return []
    rooms = list(active.select_for_update(no_key=True).order_by("pk"))
    return None if room_id is not None and not rooms else rooms


def _free_clinician_ids(pool: list[ClinicianProfile], slot: PlacementSlot) -> set[UUID]:
    schedules = load_schedules(
        [clinician.pk for clinician in pool], slot.slot_type, slot.window, slot.now
    )
    offers = free_slots_by_start(schedules, slot.slot_type, slot.window, slot.now, slot.zone)
    if isinstance(offers, QueryTooWide):
        raise ValueError("a placement window is one appointment long")
    return {
        clinician_id
        for offer in offers
        if offer.start == slot.window.starts_at
        for clinician_id in offer.clinician_ids
    }


def _choose_clinician(
    pool: list[ClinicianProfile], free_ids: set[UUID], parties: BookingParties, slot: PlacementSlot
) -> ClinicianProfile | Failure:
    if parties.clinician_id is not None:
        return pool[0]
    candidates = [
        Candidate(clinician.pk, clinician.round_robin_weight, clinician.last_assigned_at)
        for clinician in pool
        if clinician.pk in free_ids
    ]
    winner = first_available(candidates, slot.now)
    if winner is None:
        return Failure.no_clinician_available()
    return next(clinician for clinician in pool if clinician.pk == winner)


def _first_refusal(
    clinician: ClinicianProfile,
    patient: User,
    parties: BookingParties,
    slot: PlacementSlot,
    slot_is_free: bool,
    actor: User,
) -> Failure | None:
    conflicts = placement_checks.find_conflicts(
        clinician.pk, patient.pk, parties.room_id, slot.window
    )
    if conflicts:
        return Failure.conflict(conflicts)
    violations = placement_checks.violated_booking_rules(
        Role(actor.role), patient.pk, slot_is_free, slot
    )
    return Failure.rule_violation(violations) if violations else None


def _choose_room(
    clinician: ClinicianProfile, rooms: list[Room], parties: BookingParties, slot: PlacementSlot
) -> Result[UUID | None]:
    in_code_order = [room.pk for room in sorted(rooms, key=lambda room: (room.code, room.pk))]
    busy = placement_checks.busy_room_ids(in_code_order, slot.window)
    needs_room = slot.appointment_type.needs_room
    return choose_room(needs_room, parties.room_id, clinician.default_room_id, in_code_order, busy)


def _book(
    clinician: ClinicianProfile,
    patient: User,
    room_id: UUID | None,
    parties: BookingParties,
    slot: PlacementSlot,
    actor: User,
) -> Result[Appointment]:
    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                patient=patient,
                clinician=clinician,
                appointment_type=slot.appointment_type,
                room_id=room_id,
                starts_at=slot.window.starts_at,
                ends_at=slot.window.ends_at,
                status=AppointmentStatus.BOOKED,
                source=parties.source,
            )
    except IntegrityError as error:
        resource = placement_checks.violated_resource(error)
        if resource is None:
            raise
        return Failure.conflict([resource])
    _record_booking(appointment, actor, slot)
    if parties.source == AppointmentSource.ROUND_ROBIN:
        _record_assignment(clinician, actor, slot.now)
    return Success(appointment)


def _record_booking(appointment: Appointment, actor: User, slot: PlacementSlot) -> None:
    ids = {
        "appointment_id": appointment.pk,
        "patient_id": appointment.patient_id,
        "clinician_id": appointment.clinician_id,
        "appointment_type_id": appointment.appointment_type_id,
    }
    if appointment.room_id is not None:
        ids["room_id"] = appointment.room_id
    statuses = {
        "appointment_status": AppointmentStatus(appointment.status),
        "source_status": AppointmentSource(appointment.source),
    }
    metadata = AuditMetadata(ids=ids, statuses=statuses)
    record_audit(
        AuditEvent("appointment.book", "Appointment", str(appointment.pk), metadata), actor
    )
    Notification.objects.create(
        recipient_id=appointment.patient_id,
        kind=NotificationKind.SCHEDULE_CHANGED,
        title=BOOKED_TITLE,
        body=booked_notification_text(appointment.starts_at, slot.zone),
        appointment=appointment,
    )


def _record_assignment(clinician: ClinicianProfile, actor: User, now: datetime) -> None:
    clinician.last_assigned_at = now
    clinician.save(update_fields=["last_assigned_at"])
    metadata = AuditMetadata(
        ids={"clinician_id": clinician.pk},
        changed_fields=changed_field_names(ClinicianProfile, ["last_assigned_at"]),
    )
    event = AuditEvent(
        "clinician.round_robin_assigned", "ClinicianProfile", str(clinician.pk), metadata
    )
    record_audit(event, actor)
