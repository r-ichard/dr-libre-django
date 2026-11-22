"""Task 21, item 15: busy cancelled times are left out in the query, so the first row is the
first that fits, however many unusable times come before it."""

from collections.abc import Iterator
from datetime import timedelta

import pytest

from scheduling.domain.failure import Success
from scheduling.domain.request_context import RequestContext
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import (
    NOW,
    SLOT,
    _admin_user,
    _booked_slot,
    _cancelled_slot,
    _entry_for,
)
from scheduling.use_cases.waitlist import MAX_SLOTS_CHECKED, offer_waitlist_entry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-busy-times", NOW)):
        yield


def returns_the_fitting_time_when_it_is_behind_more_busy_times_than_the_scan_limit() -> None:
    clinic = make_clinic()
    _booked_slot(clinic, SLOT, ends_at=SLOT + timedelta(hours=2))
    for minute in range(MAX_SLOTS_CHECKED + 1):
        _cancelled_slot(clinic, SLOT + timedelta(minutes=minute))
    fitting = _cancelled_slot(clinic, SLOT + timedelta(hours=3))
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    entry.refresh_from_db()
    assert isinstance(result, Success)
    assert entry.offered_appointment_id == fitting.pk


def returns_the_second_time_when_the_clinician_has_time_off_over_the_first() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    make(
        "TimeOff",
        clinician=clinic.clinician,
        starts_at=SLOT - timedelta(hours=1),
        ends_at=SLOT + timedelta(hours=1),
    )
    second = _cancelled_slot(clinic, SLOT + timedelta(hours=2))
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    entry.refresh_from_db()
    assert isinstance(result, Success)
    assert entry.offered_appointment_id == second.pk
