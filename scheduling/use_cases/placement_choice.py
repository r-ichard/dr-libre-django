"""Section 5.5: which clinician and which room a placement takes, split from placement for size."""

from uuid import UUID

from scheduling.domain.failure import Failure, Result
from scheduling.domain.first_available import Candidate, first_available
from scheduling.domain.placement_rules import choose_room
from scheduling.domain.slot_search import QueryTooWide, free_slots_by_start
from scheduling.models import ClinicianProfile, Room
from scheduling.use_cases import placement_checks
from scheduling.use_cases.placement_checks import PlacementSlot
from scheduling.use_cases.schedule_loading import load_schedules


def free_clinician_ids(
    pool: list[ClinicianProfile],
    slot: PlacementSlot,
    ignored_id: UUID | None,
    ignored_hold_id: UUID | None = None,
) -> set[UUID]:
    schedules = load_schedules(
        [clinician.pk for clinician in pool],
        slot.slot_type,
        slot.window,
        slot.now,
        ignored_id,
        ignored_hold_id,
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


def choose_clinician(
    pool: list[ClinicianProfile],
    free_ids: set[UUID],
    named_clinician_id: UUID | None,
    slot: PlacementSlot,
) -> ClinicianProfile | Failure:
    if named_clinician_id is not None:
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


def choose_free_room(
    clinician: ClinicianProfile,
    rooms: list[Room],
    named_room_id: UUID | None,
    slot: PlacementSlot,
    current_room_id: UUID | None,
    replacing_id: UUID | None,
) -> Result[UUID | None]:
    in_code_order = [room.pk for room in sorted(rooms, key=lambda room: (room.code, room.pk))]
    busy = placement_checks.busy_room_ids(in_code_order, slot.window, replacing_id)
    # A moved appointment keeps its room when that room is free at the new time.
    preferred = current_room_id or clinician.default_room_id
    return choose_room(
        slot.appointment_type.needs_room, named_room_id, preferred, in_code_order, busy
    )
