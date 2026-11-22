"""Sections 5.2 step 5, 5.4 and 11: who may book for whom, which room, the notification text."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import AppointmentSource, Role


@dataclass(frozen=True)
class BookingActor:
    role: Role
    user_id: UUID
    clinician_id: UUID | None


@dataclass(frozen=True)
class NamedParties:
    patient_id: UUID | None
    clinician_id: UUID | None
    room_id: UUID | None


@dataclass(frozen=True)
class BookingParties:
    patient_id: UUID
    clinician_id: UUID | None
    room_id: UUID | None
    source: AppointmentSource


def authorize_booking(actor: BookingActor, named: NamedParties) -> Result[BookingParties]:
    if actor.role == Role.PATIENT:
        return _patient_books(actor, named)
    if actor.role == Role.CLINICIAN:
        return _clinician_books(actor, named)
    return _admin_books(named)


def _patient_books(actor: BookingActor, named: NamedParties) -> Result[BookingParties]:
    if named.patient_id not in (None, actor.user_id) or named.room_id is not None:
        return Failure.forbidden()
    source = AppointmentSource.ONLINE if named.clinician_id else AppointmentSource.ROUND_ROBIN
    return Success(BookingParties(actor.user_id, named.clinician_id, None, source))


def _clinician_books(actor: BookingActor, named: NamedParties) -> Result[BookingParties]:
    if actor.clinician_id is None or named.clinician_id not in (None, actor.clinician_id):
        return Failure.forbidden()
    if named.patient_id is None:
        return Failure.invalid_input([FieldMessage("patient_id", "A patient is required.")])
    return Success(
        BookingParties(named.patient_id, actor.clinician_id, named.room_id, AppointmentSource.STAFF)
    )


def _admin_books(named: NamedParties) -> Result[BookingParties]:
    missing = [
        FieldMessage(name, message)
        for name, message, value in (
            ("patient_id", "A patient is required.", named.patient_id),
            ("clinician_id", "A clinician is required.", named.clinician_id),
        )
        if value is None
    ]
    if missing or named.patient_id is None:
        return Failure.invalid_input(missing)
    return Success(
        BookingParties(named.patient_id, named.clinician_id, named.room_id, AppointmentSource.STAFF)
    )


def choose_room(
    needs_room: bool,
    named_room_id: UUID | None,
    default_room_id: UUID | None,
    rooms_in_code_order: Sequence[UUID],
    busy_room_ids: Collection[UUID],
) -> Result[UUID | None]:
    if not needs_room:
        return Success(None)
    if named_room_id is not None:
        return Success(named_room_id)
    if default_room_id in rooms_in_code_order and default_room_id not in busy_room_ids:
        return Success(default_room_id)
    free_rooms = [room_id for room_id in rooms_in_code_order if room_id not in busy_room_ids]
    return Success(free_rooms[0]) if free_rooms else Failure.no_room_available()


def booked_notification_text(starts_at: datetime, time_zone: ZoneInfo) -> str:
    local = starts_at.astimezone(time_zone)
    return f"Your appointment is on {local:%Y-%m-%d} at {local:%H:%M} ({time_zone.key})."


def _written_time(starts_at: datetime, time_zone: ZoneInfo) -> str:
    local = starts_at.astimezone(time_zone)
    return f"{local:%A} {local.day} {local:%B %Y}, {local:%H:%M} ({time_zone.key})"


def cancelled_notification_text(starts_at: datetime, time_zone: ZoneInfo) -> str:
    return f"Your appointment on {_written_time(starts_at, time_zone)} is cancelled."


def rescheduled_notification_text(starts_at: datetime, time_zone: ZoneInfo) -> str:
    return f"Your appointment has moved to {_written_time(starts_at, time_zone)}."
