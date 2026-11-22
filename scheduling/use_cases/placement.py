"""Sections 5.2, 5.4, 5.5: the one use case every booking path calls to place an appointment.

Lock order, global against deadlock: clinicians by id, patient, rooms by id. Checks run after
all locks; the exclusion constraints stay the last line."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction

from scheduling.domain.audit_metadata import AuditMetadata, EmailDomain
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.placement_rules import (
    BookingActor,
    BookingParties,
    NamedParties,
    authorize_booking,
)
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, Role
from scheduling.models import (
    Appointment,
    ClinicianProfile,
    Room,
    User,
)
from scheduling.models.booking import NotificationKind
from scheduling.use_cases import placement_checks
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.notifications import BOOKED_TITLE, notify_patient
from scheduling.use_cases.placement_checks import PlacementSlot, slot_of
from scheduling.use_cases.placement_choice import (
    choose_clinician,
    choose_free_room,
    free_clinician_ids,
)
from scheduling.use_cases.placement_locks import lock_clinicians, lock_patient, lock_rooms
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.schedule_loading import active_appointment_type, online_only_for


@dataclass(frozen=True)
class HoldClaim:
    """A visitor's own hold, placed on their behalf: it is left out of the conflict check, it sets
    the source of the appointment, and its email domain goes into the booking's audit entry."""

    hold_id: UUID
    source: AppointmentSource
    email_domain: EmailDomain


@dataclass(frozen=True)
class PlacementCommand:
    appointment_type_id: UUID
    starts_at: datetime
    clinician_id: UUID | None
    patient_id: UUID | None
    room_id: UUID | None
    reason: str = ""
    via_hold: HoldClaim | None = None
    announce: bool = True


@dataclass(frozen=True)
class Probe:
    clinician: ClinicianProfile
    ends_at: datetime


def place_appointment(command: PlacementCommand, actor: User) -> Result[Appointment]:
    named = NamedParties(command.patient_id, command.clinician_id, command.room_id)
    authorized = authorize_booking(_booking_actor(actor), named)
    if isinstance(authorized, Failure):
        return authorized
    parties = authorized.value
    if command.via_hold is not None:
        parties = replace(parties, source=command.via_hold.source)
    with transaction.atomic():
        return _place(command, actor, parties)


def probe_placement(command: PlacementCommand, ignoring_hold_id: UUID | None) -> Result[Probe]:
    """The placement checks for a patient who does not exist yet. The two that read a patient's own
    appointments wait for the verified code, so the answer cannot tell an account from a new
    address. Returns the clinician it would take and the slot end."""
    with transaction.atomic():
        request = _Request(command, command.clinician_id, None, None, None, ignoring_hold_id)
        selected = _select(request)
        if isinstance(selected, Failure):
            return selected
        chosen = selected.value
        return Success(Probe(chosen.clinician, chosen.context.slot.window.ends_at))


def replace_placement(
    appointment: Appointment, starts_at: datetime, actor: User
) -> Result[Appointment]:
    """Moves an appointment to a new start through the same checks as a booking. The caller holds
    the appointment's lock inside its transaction."""
    command = PlacementCommand(
        appointment.appointment_type_id,
        starts_at,
        appointment.clinician_id,
        appointment.patient_id,
        None,
    )
    source = AppointmentSource(appointment.source)
    parties = BookingParties(appointment.patient_id, appointment.clinician_id, None, source)
    return _place(command, actor, parties, appointment)


def _booking_actor(actor: User) -> BookingActor:
    role = Role(actor.role)
    clinician_id = None
    if role == Role.CLINICIAN:
        profiles = ClinicianProfile.objects.filter(user_id=actor.pk)
        clinician_id = profiles.values_list("pk", flat=True).first()
    return BookingActor(role, actor.pk, clinician_id)


@dataclass(frozen=True)
class _Request:
    """What one run of the checks needs. No actor and no patient id is a probe for a visitor."""

    command: PlacementCommand
    clinician_id: UUID | None
    room_id: UUID | None
    actor: User | None
    patient_id: UUID | None
    ignoring_hold_id: UUID | None
    replacing: Appointment | None = None


@dataclass(frozen=True)
class ChangeContext:
    slot: PlacementSlot
    slot_is_free: bool
    actor: User | None
    replacing: Appointment | None
    reason: str = ""
    email_domain: EmailDomain | None = None
    announce: bool = True

    @property
    def replacing_id(self) -> UUID | None:
        return self.replacing.pk if self.replacing is not None else None

    @property
    def actor_role(self) -> Role:
        return Role(self.actor.role) if self.actor is not None else Role.PATIENT


@dataclass(frozen=True)
class _Selection:
    clinician: ClinicianProfile
    patient: User | None
    room_id: UUID | None
    context: ChangeContext


def _place(
    command: PlacementCommand,
    actor: User,
    parties: BookingParties,
    replacing: Appointment | None = None,
) -> Result[Appointment]:
    hold_id = command.via_hold.hold_id if command.via_hold is not None else None
    request = _Request(
        command,
        parties.clinician_id,
        parties.room_id,
        actor,
        parties.patient_id,
        hold_id,
        replacing,
    )
    selected = _select(request)
    if isinstance(selected, Failure):
        return selected
    chosen = selected.value
    if chosen.patient is None:
        raise ValueError("a placement for an actor has a patient")
    return _book(chosen, chosen.patient, parties, actor)


def _select(request: _Request) -> Result[_Selection]:
    command = request.command
    # The type stays visible here: the booking rules answer a typed rule_violation for it.
    appointment_type = active_appointment_type(command.appointment_type_id, online_only=False)
    if appointment_type is None:
        return Failure.not_found()
    pool = lock_clinicians(appointment_type, request.clinician_id, online_only_for(request.actor))
    patient = None if request.patient_id is None else lock_patient(request.patient_id)
    rooms = lock_rooms(appointment_type, request.room_id)
    named_clinician_missing = request.clinician_id is not None and not pool
    patient_missing = request.patient_id is not None and patient is None
    if named_clinician_missing or patient_missing or rooms is None:
        return Failure.not_found()
    if not appointment_type.needs_room:
        # Section 5.2 step 5: a type with no room need gets none; the name was checked above.
        request = replace(request, room_id=None)
    now = current_request_context().now
    slot = slot_of(appointment_type, command.starts_at, now)
    replacing_id = request.replacing.pk if request.replacing is not None else None
    free_ids = free_clinician_ids(pool, slot, replacing_id, request.ignoring_hold_id)
    chosen = choose_clinician(pool, free_ids, request.clinician_id, slot)
    if isinstance(chosen, Failure):
        return chosen
    email_domain = command.via_hold.email_domain if command.via_hold is not None else None
    context = ChangeContext(
        slot,
        chosen.pk in free_ids,
        request.actor,
        request.replacing,
        command.reason,
        email_domain,
        command.announce,
    )
    refused = _first_refusal(chosen, patient, request, context)
    if refused is not None:
        return refused
    room_id = _choose_room(chosen, rooms, request, context)
    if isinstance(room_id, Failure):
        return room_id
    return Success(_Selection(chosen, patient, room_id.value, context))


def _first_refusal(
    clinician: ClinicianProfile, patient: User | None, request: _Request, context: ChangeContext
) -> Failure | None:
    replacing, slot = context.replacing, context.slot
    held = placement_checks.clinician_is_held(
        clinician.pk, slot.window, slot.now, request.ignoring_hold_id
    )
    conflicts = placement_checks.find_conflicts(
        clinician.pk,
        patient.pk if patient is not None else None,
        request.room_id,
        slot.window,
        context.replacing_id,
        held,
    )
    if conflicts:
        return Failure.conflict(conflicts)
    violations = placement_checks.violated_booking_rules(
        context.actor_role,
        patient.pk if patient is not None else None,
        context.slot_is_free,
        slot,
        replacing.starts_at if replacing is not None else None,
    )
    return Failure.rule_violation(violations) if violations else None


def _choose_room(
    clinician: ClinicianProfile, rooms: list[Room], request: _Request, context: ChangeContext
) -> Result[UUID | None]:
    replacing = context.replacing
    current_room_id = replacing.room_id if replacing is not None else None
    return choose_free_room(
        clinician, rooms, request.room_id, context.slot, current_room_id, context.replacing_id
    )


def _book(
    chosen: _Selection, patient: User, parties: BookingParties, actor: User
) -> Result[Appointment]:
    clinician, context = chosen.clinician, chosen.context
    slot, replacing = context.slot, context.replacing
    try:
        with transaction.atomic():
            appointment = _write(chosen, patient, parties.source)
    except IntegrityError as error:
        resource = placement_checks.violated_resource(error)
        if resource is None:
            raise
        return Failure.conflict([resource])
    if replacing is not None:
        return Success(appointment)
    _record_booking(appointment, actor, context)
    if parties.source == AppointmentSource.ROUND_ROBIN:
        _record_assignment(clinician, actor, slot.now)
    return Success(appointment)


def _write(chosen: _Selection, patient: User, source: AppointmentSource) -> Appointment:
    clinician, room_id, context = chosen.clinician, chosen.room_id, chosen.context
    window = context.slot.window
    if context.replacing is None:
        return Appointment.objects.create(
            patient=patient,
            clinician=clinician,
            appointment_type=context.slot.appointment_type,
            room_id=room_id,
            starts_at=window.starts_at,
            ends_at=window.ends_at,
            status=AppointmentStatus.BOOKED,
            source=source,
            patient_reason=context.reason,
        )
    moved = context.replacing
    moved.room_id, moved.starts_at, moved.ends_at = room_id, window.starts_at, window.ends_at
    moved.save()
    return moved


def _record_booking(appointment: Appointment, actor: User, context: ChangeContext) -> None:
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
    metadata = AuditMetadata(ids=ids, statuses=statuses, email_domain=context.email_domain)
    record_audit(
        AuditEvent("appointment.book", "Appointment", str(appointment.pk), metadata), actor
    )
    if context.announce:
        notify_patient(appointment, NotificationKind.SCHEDULE_CHANGED, BOOKED_TITLE)


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
