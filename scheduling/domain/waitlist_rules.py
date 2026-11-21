"""Sections 5.7 and 5.8: matching a freed slot, offering a cancelled one, joining, going stale and
the reminder window. Pure functions over ids and instants."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import AppointmentStatus, Role, WaitlistStatus


@dataclass(frozen=True)
class WaitingEntry:
    entry_id: UUID
    created_at: datetime
    preferred_clinician_id: UUID | None
    earliest_at: datetime
    latest_at: datetime


@dataclass(frozen=True)
class FreedSlot:
    clinician_id: UUID
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class CancelledSlot:
    appointment_id: UUID
    clinician_id: UUID
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class WaitlistSnapshot:
    status: WaitlistStatus
    latest_at: datetime
    offered_starts_at: datetime | None
    offered_slot_taken: bool


class ExpiryDecision(StrEnum):
    KEEP = "KEEP"
    EXPIRE = "EXPIRE"
    RELEASE = "RELEASE"


REMINDER_LEAD = timedelta(hours=24)
REMINDED_STATUSES = frozenset({AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED})


def _window_holds(
    earliest_at: datetime,
    latest_at: datetime,
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
) -> bool:
    return starts_at > now and earliest_at <= starts_at and ends_at <= latest_at


def entry_matches_slot(entry: WaitingEntry, slot: FreedSlot, now: datetime) -> bool:
    clinician_fits = entry.preferred_clinician_id in (None, slot.clinician_id)
    return clinician_fits and _window_holds(
        entry.earliest_at, entry.latest_at, slot.starts_at, slot.ends_at, now
    )


def best_match(entries: list[WaitingEntry], slot: FreedSlot, now: datetime) -> UUID | None:
    matching = [entry for entry in entries if entry_matches_slot(entry, slot, now)]
    if not matching:
        return None
    return min(matching, key=lambda entry: (entry.created_at, entry.entry_id)).entry_id


def first_offerable_slot(
    entry: WaitingEntry, slots: list[CancelledSlot], held_ids: set[UUID], now: datetime
) -> UUID | None:
    offerable = [
        slot
        for slot in slots
        if slot.appointment_id not in held_ids
        and entry.preferred_clinician_id in (None, slot.clinician_id)
        and _window_holds(entry.earliest_at, entry.latest_at, slot.starts_at, slot.ends_at, now)
    ]
    if not offerable:
        return None
    return min(offerable, key=lambda slot: (slot.starts_at, slot.appointment_id)).appointment_id


def authorize_join(role: Role, user_id: UUID, named_patient_id: UUID | None) -> Result[UUID]:
    if role == Role.PATIENT:
        if named_patient_id not in (None, user_id):
            return Failure.forbidden()
        return Success(user_id)
    if role == Role.ADMIN:
        if named_patient_id is None:
            return Failure.invalid_input([FieldMessage("patient_id", "A patient is required.")])
        return Success(named_patient_id)
    return Failure.forbidden()


def expiry_decision(snapshot: WaitlistSnapshot, now: datetime) -> ExpiryDecision:
    window_closed = snapshot.latest_at < now
    if snapshot.status == WaitlistStatus.WAITING:
        return ExpiryDecision.EXPIRE if window_closed else ExpiryDecision.KEEP
    if snapshot.status != WaitlistStatus.OFFERED or snapshot.offered_starts_at is None:
        return ExpiryDecision.KEEP
    offer_stale = snapshot.offered_slot_taken or snapshot.offered_starts_at <= now
    if not offer_stale:
        return ExpiryDecision.KEEP
    return ExpiryDecision.EXPIRE if window_closed else ExpiryDecision.RELEASE


def is_reminder_due(status: AppointmentStatus, starts_at: datetime, now: datetime) -> bool:
    return status in REMINDED_STATUSES and now < starts_at <= now + REMINDER_LEAD
