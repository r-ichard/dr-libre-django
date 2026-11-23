"""Section 5.8: an offer needs the clinician, the room and the patient free, at the offer
and again when the job checks whether it went stale."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Department, Room, WaitlistEntry
from scheduling.models.builders import Clinic, add_clinician, make, make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import (
    NOW,
    SLOT,
    _admin_user,
    _booked_slot,
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.use_cases.waitlist import offer_waitlist_entry
from scheduling.use_cases.waitlist_expiry import expire_waitlist

pytestmark = pytest.mark.django_db

ONE_HOUR = timedelta(hours=1)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-offer-fit", NOW)):
        yield


def _room_of(clinic_department: Department) -> Room:
    room = make("Room", department=clinic_department)
    assert isinstance(room, Room)
    return room


def returns_offered_when_first_slot_clinician_is_busy_but_the_second_fits() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    _booked_slot(clinic)
    second = _cancelled_slot(clinic, SLOT + 2 * ONE_HOUR)
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    entry.refresh_from_db()
    assert isinstance(result, Success)
    assert entry.offered_appointment_id == second.pk


def returns_conflict_room_when_the_cancelled_slots_room_is_taken() -> None:
    clinic = make_clinic()
    room = _room_of(clinic.department)
    _cancelled_slot(clinic, room=room)
    _booked_slot(_second_clinic(clinic), room=room)
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    assert result == Failure.conflict(["room"])
    entry.refresh_from_db()
    assert entry.status == "WAITING"


def returns_conflict_patient_when_the_entry_patient_has_another_appointment_then() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    _booked_slot(_second_clinic(clinic), patient=clinic.patient)
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    assert result == Failure.conflict(["patient"])


def returns_conflict_offer_when_another_entry_holds_the_only_slot() -> None:
    clinic = make_clinic()
    held = _cancelled_slot(clinic)
    _offered_entry(clinic, held, patient=make("User"))
    entry = _entry_for(clinic)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    assert result == Failure.conflict(["offer"])


def returns_waiting_when_the_offered_slots_room_is_taken_and_the_window_is_open() -> None:
    clinic = make_clinic()
    room = _room_of(clinic.department)
    entry = _offered_entry(clinic, _cancelled_slot(clinic, room=room))
    _booked_slot(_second_clinic(clinic), room=room)

    count = expire_waitlist()

    entry.refresh_from_db()
    assert (count, entry.status, entry.offered_appointment_id) == (1, "WAITING", None)


def returns_waiting_when_the_entry_patient_took_another_appointment_then() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    _booked_slot(_second_clinic(clinic), patient=clinic.patient)

    count = expire_waitlist()

    entry.refresh_from_db()
    assert (count, entry.status) == (1, "WAITING")
    assert WaitlistEntry.objects.get(pk=entry.pk).offered_appointment_id is None


def _second_clinic(clinic: Clinic) -> Clinic:
    """Another clinician of the same department, so only the room or the patient is shared."""
    return replace(clinic, clinician=add_clinician(clinic.department))


def returns_no_clinician_available_when_the_only_slot_starts_before_the_window() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic, earliest_at=SLOT + ONE_HOUR, latest_at=SLOT + 3 * ONE_HOUR)

    assert offer_waitlist_entry(entry.pk, _admin_user()) == Failure.no_clinician_available()
