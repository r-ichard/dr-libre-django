"""Sections 5.7 and 5.8: matching a freed slot, offering a cancelled one, joining, going stale and
the reminder window. Pure functions over ids and instants."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from scheduling.domain.failure import Failure, Success
from scheduling.domain.vocabulary import AppointmentStatus, Role, WaitlistStatus
from scheduling.domain.waitlist_rules import (
    CancelledSlot,
    ExpiryDecision,
    FreedSlot,
    WaitingEntry,
    WaitlistSnapshot,
    authorize_join,
    best_match,
    entry_matches_slot,
    expiry_decision,
    first_offerable_slot,
    is_reminder_due,
)

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SLOT_START = NOW + timedelta(days=2)
SLOT_END = SLOT_START + timedelta(minutes=30)
CLINICIAN_ID = uuid4()
OTHER_CLINICIAN_ID = uuid4()
PATIENT_ID = uuid4()
OTHER_PATIENT_ID = uuid4()
ONE_DAY = timedelta(days=1)
ONE_SECOND = timedelta(seconds=1)


def _entry(number: int, **overrides: object) -> WaitingEntry:
    fields: dict[str, object] = {
        "entry_id": UUID(int=number),
        "created_at": NOW - timedelta(hours=number),
        "preferred_clinician_id": None,
        "earliest_at": SLOT_START - ONE_DAY,
        "latest_at": SLOT_END + ONE_DAY,
    }
    return WaitingEntry(**{**fields, **overrides})  # type: ignore[arg-type]


def _slot(**overrides: object) -> FreedSlot:
    fields: dict[str, object] = {
        "clinician_id": CLINICIAN_ID,
        "starts_at": SLOT_START,
        "ends_at": SLOT_END,
    }
    return FreedSlot(**{**fields, **overrides})  # type: ignore[arg-type]


def _cancelled(number: int, **overrides: object) -> CancelledSlot:
    fields: dict[str, object] = {
        "appointment_id": UUID(int=number),
        "clinician_id": CLINICIAN_ID,
        "starts_at": SLOT_START,
        "ends_at": SLOT_END,
    }
    return CancelledSlot(**{**fields, **overrides})  # type: ignore[arg-type]


# --- best_match ---


def returns_oldest_entry_when_two_match() -> None:
    older = _entry(1, created_at=NOW - timedelta(hours=9))
    newer = _entry(2, created_at=NOW - timedelta(hours=1))

    assert best_match([newer, older], _slot(), NOW) == older.entry_id


def returns_lowest_id_when_created_at_ties() -> None:
    tied = NOW - timedelta(hours=3)
    higher = _entry(7, created_at=tied)
    lower = _entry(4, created_at=tied)

    assert best_match([higher, lower], _slot(), NOW) == lower.entry_id


def returns_none_when_preferred_clinician_is_another() -> None:
    entry = _entry(1, preferred_clinician_id=OTHER_CLINICIAN_ID)

    assert best_match([entry], _slot(), NOW) is None


def returns_entry_when_preferred_clinician_is_the_freed_one() -> None:
    entry = _entry(1, preferred_clinician_id=CLINICIAN_ID)

    assert best_match([entry], _slot(), NOW) == entry.entry_id


def returns_entry_when_preferred_clinician_empty() -> None:
    entry = _entry(1, preferred_clinician_id=None)

    assert best_match([entry], _slot(), NOW) == entry.entry_id


def returns_none_when_no_entries() -> None:
    assert best_match([], _slot(), NOW) is None


def returns_younger_matching_entry_when_older_one_does_not_match() -> None:
    older_elsewhere = _entry(
        1, created_at=NOW - timedelta(hours=9), preferred_clinician_id=OTHER_CLINICIAN_ID
    )
    younger = _entry(2, created_at=NOW - timedelta(hours=1))

    assert best_match([older_elsewhere, younger], _slot(), NOW) == younger.entry_id


# --- entry_matches_slot ---


def returns_none_when_slot_ends_after_latest_at() -> None:
    entry = _entry(1, latest_at=SLOT_END - ONE_SECOND)

    assert entry_matches_slot(entry, _slot(), NOW) is False


def returns_entry_when_slot_fits_window_exactly() -> None:
    entry = _entry(1, earliest_at=SLOT_START, latest_at=SLOT_END)

    assert entry_matches_slot(entry, _slot(), NOW) is True


def returns_false_when_slot_starts_before_earliest_at() -> None:
    entry = _entry(1, earliest_at=SLOT_START + ONE_SECOND)

    assert entry_matches_slot(entry, _slot(), NOW) is False


def returns_false_when_slot_start_is_now() -> None:
    slot = _slot(starts_at=NOW, ends_at=NOW + timedelta(minutes=30))
    entry = _entry(1, earliest_at=NOW - ONE_DAY)

    assert entry_matches_slot(entry, slot, NOW) is False


def returns_true_when_slot_starts_one_second_after_now() -> None:
    slot = _slot(starts_at=NOW + ONE_SECOND, ends_at=NOW + timedelta(minutes=30))
    entry = _entry(1, earliest_at=NOW - ONE_DAY)

    assert entry_matches_slot(entry, slot, NOW) is True


# --- first_offerable_slot ---


def returns_earliest_slot_when_several_cancelled() -> None:
    later = _cancelled(
        1, starts_at=SLOT_START + timedelta(hours=2), ends_at=SLOT_END + timedelta(hours=2)
    )
    earlier = _cancelled(2)

    assert first_offerable_slot(_entry(1), [later, earlier], set(), NOW) == earlier.appointment_id


def returns_lowest_id_when_slot_starts_tie() -> None:
    higher = _cancelled(9)
    lower = _cancelled(3)

    assert first_offerable_slot(_entry(1), [higher, lower], set(), NOW) == lower.appointment_id


def returns_none_when_slot_past() -> None:
    past = _cancelled(1, starts_at=NOW - timedelta(hours=1), ends_at=NOW - timedelta(minutes=30))
    entry = _entry(1, earliest_at=NOW - ONE_DAY)

    assert first_offerable_slot(entry, [past], set(), NOW) is None


def returns_next_slot_when_first_is_held_by_another_entry() -> None:
    held = _cancelled(1)
    free = _cancelled(
        2, starts_at=SLOT_START + timedelta(hours=1), ends_at=SLOT_END + timedelta(hours=1)
    )

    assert (
        first_offerable_slot(_entry(1), [held, free], {held.appointment_id}, NOW)
        == free.appointment_id
    )


def returns_none_when_slot_outside_window() -> None:
    outside = _cancelled(
        1, starts_at=SLOT_START + timedelta(days=5), ends_at=SLOT_END + timedelta(days=5)
    )

    assert first_offerable_slot(_entry(1), [outside], set(), NOW) is None


def returns_none_when_slot_belongs_to_another_preferred_clinician() -> None:
    entry = _entry(1, preferred_clinician_id=OTHER_CLINICIAN_ID)

    assert first_offerable_slot(entry, [_cancelled(1)], set(), NOW) is None


# --- authorize_join ---


def returns_own_id_when_patient_joins_for_self() -> None:
    assert authorize_join(Role.PATIENT, PATIENT_ID, None) == Success(PATIENT_ID)


def returns_own_id_when_patient_names_self() -> None:
    assert authorize_join(Role.PATIENT, PATIENT_ID, PATIENT_ID) == Success(PATIENT_ID)


def returns_forbidden_when_patient_names_other_patient() -> None:
    assert authorize_join(Role.PATIENT, PATIENT_ID, OTHER_PATIENT_ID) == Failure.forbidden()


def returns_forbidden_when_clinician_joins() -> None:
    assert authorize_join(Role.CLINICIAN, uuid4(), PATIENT_ID) == Failure.forbidden()


def returns_named_patient_when_admin_joins_for_patient() -> None:
    assert authorize_join(Role.ADMIN, uuid4(), PATIENT_ID) == Success(PATIENT_ID)


def returns_invalid_input_when_admin_names_no_patient() -> None:
    result = authorize_join(Role.ADMIN, uuid4(), None)

    assert isinstance(result, Failure)
    assert result.details["fields"] == [
        {"field": "patient_id", "message": "A patient is required."}
    ]


# --- expiry_decision ---


def _snapshot(status: WaitlistStatus, **overrides: object) -> WaitlistSnapshot:
    fields: dict[str, object] = {
        "status": status,
        "latest_at": NOW + ONE_DAY,
        "offered_starts_at": None,
        "offered_slot_taken": False,
    }
    return WaitlistSnapshot(**{**fields, **overrides})  # type: ignore[arg-type]


def returns_expired_when_waiting_latest_passed() -> None:
    snapshot = _snapshot(WaitlistStatus.WAITING, latest_at=NOW - ONE_SECOND)

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.EXPIRE


def returns_keep_when_waiting_latest_is_exactly_now() -> None:
    assert (
        expiry_decision(_snapshot(WaitlistStatus.WAITING, latest_at=NOW), NOW)
        == ExpiryDecision.KEEP
    )


def returns_keep_when_waiting_latest_in_future() -> None:
    assert expiry_decision(_snapshot(WaitlistStatus.WAITING), NOW) == ExpiryDecision.KEEP


def returns_release_when_offered_slot_passed_and_window_open() -> None:
    snapshot = _snapshot(WaitlistStatus.OFFERED, offered_starts_at=NOW)

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.RELEASE


def returns_release_when_offered_slot_taken_and_window_open() -> None:
    snapshot = _snapshot(
        WaitlistStatus.OFFERED, offered_starts_at=NOW + timedelta(hours=5), offered_slot_taken=True
    )

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.RELEASE


def returns_expired_when_offered_slot_taken_and_window_closed() -> None:
    snapshot = _snapshot(
        WaitlistStatus.OFFERED,
        latest_at=NOW - ONE_SECOND,
        offered_starts_at=NOW + timedelta(hours=5),
        offered_slot_taken=True,
    )

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.EXPIRE


def returns_expired_when_offered_slot_passed_and_window_closed() -> None:
    snapshot = _snapshot(
        WaitlistStatus.OFFERED, latest_at=NOW - ONE_SECOND, offered_starts_at=NOW - ONE_SECOND
    )

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.EXPIRE


def returns_keep_when_offered_slot_is_future_and_free_even_if_latest_passed() -> None:
    snapshot = _snapshot(
        WaitlistStatus.OFFERED,
        latest_at=NOW - ONE_SECOND,
        offered_starts_at=NOW + ONE_SECOND,
    )

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.KEEP


def returns_keep_when_entry_is_booked_or_expired() -> None:
    decisions = [
        expiry_decision(_snapshot(status, latest_at=NOW - ONE_DAY), NOW)
        for status in (WaitlistStatus.BOOKED, WaitlistStatus.EXPIRED)
    ]

    assert decisions == [ExpiryDecision.KEEP, ExpiryDecision.KEEP]


def returns_keep_when_booked_entry_still_carries_a_past_offered_slot() -> None:
    snapshot = _snapshot(
        WaitlistStatus.BOOKED,
        latest_at=NOW + ONE_DAY,
        offered_starts_at=NOW - ONE_DAY,
        offered_slot_taken=True,
    )

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.KEEP


def returns_keep_when_offered_entry_has_no_offered_start() -> None:
    snapshot = _snapshot(WaitlistStatus.OFFERED, latest_at=NOW - ONE_DAY, offered_slot_taken=True)

    assert expiry_decision(snapshot, NOW) == ExpiryDecision.KEEP


# --- is_reminder_due ---


def returns_due_when_booked_appointment_starts_exactly_24_hours_ahead() -> None:
    assert is_reminder_due(AppointmentStatus.BOOKED, NOW + ONE_DAY, NOW) is True


def returns_not_due_when_appointment_starts_24_hours_and_one_second_ahead() -> None:
    assert is_reminder_due(AppointmentStatus.BOOKED, NOW + ONE_DAY + ONE_SECOND, NOW) is False


def returns_due_when_confirmed_appointment_starts_in_one_hour() -> None:
    assert is_reminder_due(AppointmentStatus.CONFIRMED, NOW + timedelta(hours=1), NOW) is True


def returns_not_due_when_appointment_cancelled() -> None:
    assert is_reminder_due(AppointmentStatus.CANCELLED, NOW + timedelta(hours=1), NOW) is False


def returns_not_due_when_appointment_started_already() -> None:
    assert is_reminder_due(AppointmentStatus.BOOKED, NOW, NOW) is False


def returns_not_due_when_status_is_checked_in() -> None:
    assert is_reminder_due(AppointmentStatus.CHECKED_IN, NOW + timedelta(hours=1), NOW) is False
