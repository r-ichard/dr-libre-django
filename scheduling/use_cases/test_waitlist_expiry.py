"""Section 5.8 expiry, and the policy for an offer that went stale: back to WAITING while the
window is open, EXPIRED once it is closed."""

from collections.abc import Iterator
from datetime import timedelta

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.models import AuditLogEntry, WaitlistEntry
from scheduling.models.builders import make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import (
    NOW,
    ONE_DAY,
    _booked_slot,
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.use_cases.waitlist_expiry import expire_waitlist

pytestmark = pytest.mark.django_db

PAST_WINDOW = {"earliest_at": NOW - 2 * ONE_DAY, "latest_at": NOW - timedelta(seconds=1)}


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-expiry", NOW)):
        yield


def _state_of(entry: WaitlistEntry) -> tuple[str, object]:
    entry.refresh_from_db()
    return entry.status, entry.offered_appointment_id


def returns_expired_when_waiting_latest_passed() -> None:
    entry = _entry_for(make_clinic(), **PAST_WINDOW)

    count = expire_waitlist()

    assert count == 1
    assert _state_of(entry) == ("EXPIRED", None)


def returns_waiting_when_latest_is_exactly_now() -> None:
    entry = _entry_for(make_clinic(), earliest_at=NOW - ONE_DAY, latest_at=NOW)

    assert expire_waitlist() == 0
    assert _state_of(entry) == ("WAITING", None)


def returns_waiting_when_latest_in_future() -> None:
    entry = _entry_for(make_clinic())

    assert expire_waitlist() == 0
    assert _state_of(entry) == ("WAITING", None)


def returns_waiting_with_offer_cleared_when_offered_slot_passed_and_window_open() -> None:
    clinic = make_clinic()
    passed = _cancelled_slot(clinic, NOW - timedelta(hours=1))
    entry = _offered_entry(clinic, passed, earliest_at=NOW - ONE_DAY, latest_at=NOW + ONE_DAY)

    count = expire_waitlist()

    assert count == 1
    assert _state_of(entry) == ("WAITING", None)


def returns_waiting_with_offer_cleared_when_offered_slot_taken_and_window_open() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    _booked_slot(clinic)

    assert expire_waitlist() == 1
    assert _state_of(entry) == ("WAITING", None)


def returns_expired_when_offered_slot_taken_and_window_closed() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic, NOW + timedelta(hours=5))
    entry = _offered_entry(
        clinic, freed, earliest_at=NOW - ONE_DAY, latest_at=NOW - timedelta(seconds=1)
    )
    _booked_slot(clinic, NOW + timedelta(hours=5))

    assert expire_waitlist() == 1
    assert _state_of(entry) == ("EXPIRED", None)


def returns_offer_kept_when_offered_slot_still_free_in_the_future() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _offered_entry(clinic, freed)

    assert expire_waitlist() == 0
    assert _state_of(entry) == ("OFFERED", freed.pk)


def returns_offer_kept_when_only_a_cancelled_appointment_overlaps_the_offered_slot() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    _cancelled_slot(clinic)
    entry = _offered_entry(clinic, freed)

    assert expire_waitlist() == 0
    assert _state_of(entry) == ("OFFERED", freed.pk)


def returns_untouched_when_entry_is_booked_or_expired() -> None:
    clinic = make_clinic()
    booked = _entry_for(clinic, status="BOOKED", **PAST_WINDOW)
    expired = _entry_for(clinic, status="EXPIRED", **PAST_WINDOW)

    assert expire_waitlist() == 0
    assert (_state_of(booked)[0], _state_of(expired)[0]) == ("BOOKED", "EXPIRED")


def returns_one_audit_entry_per_changed_entry() -> None:
    clinic = make_clinic()
    _entry_for(clinic, **PAST_WINDOW)
    _entry_for(clinic, **PAST_WINDOW)
    stale = _offered_entry(clinic, _cancelled_slot(clinic, NOW - timedelta(hours=1)))

    expire_waitlist()

    actions = sorted(AuditLogEntry.objects.values_list("action", flat=True))
    assert actions == ["waitlist.expire", "waitlist.expire", "waitlist.release"]
    release = AuditLogEntry.objects.get(action="waitlist.release")
    assert release.entity_id == str(stale.pk)
    assert release.actor_id is None


def returns_zero_and_no_audit_when_nothing_is_stale() -> None:
    _entry_for(make_clinic())

    assert expire_waitlist() == 0
    assert AuditLogEntry.objects.count() == 0
