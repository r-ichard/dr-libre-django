"""Section 5.2 and 7.1: a live hold is a conflict on its clinician, for everyone but its owner."""

from collections.abc import Iterator

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.models import Appointment
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.test_booking_support import NOW, SLOT, TEN_MINUTES, THIRTY_MINUTES, _at

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def _hold_on(clinic: object, expires_at: object) -> None:
    make(
        "BookingHold",
        clinician=clinic.clinician,  # type: ignore[attr-defined]
        appointment_type=clinic.appointment_type,  # type: ignore[attr-defined]
        starts_at=SLOT,
        ends_at=SLOT + THIRTY_MINUTES,
        expires_at=expires_at,
    )


def _place(clinic: object) -> object:
    command = PlacementCommand(
        clinic.appointment_type.pk,  # type: ignore[attr-defined]
        SLOT,
        clinic.clinician.pk,  # type: ignore[attr-defined]
        None,
        None,
    )
    return place_appointment(command, clinic.patient)  # type: ignore[attr-defined]


def returns_conflict_on_clinician_when_slot_is_held_by_a_visitor() -> None:
    clinic = make_clinic()
    _hold_on(clinic, NOW + TEN_MINUTES)

    result = _place(clinic)

    assert result == Failure.conflict(["clinician"])
    assert Appointment.objects.count() == 0


def returns_booking_when_the_hold_expired_exactly_now() -> None:
    clinic = make_clinic()
    _hold_on(clinic, NOW + TEN_MINUTES)

    with _at(NOW + TEN_MINUTES):
        result = _place(clinic)

    assert isinstance(result, Success)


def returns_booking_when_the_hold_is_on_another_clinician() -> None:
    clinic = make_clinic()
    other = make_clinic()
    _hold_on(other, NOW + TEN_MINUTES)

    assert isinstance(_place(clinic), Success)
