"""Section 5.2 step 3: the database refuses two active appointments that overlap in time for the
same clinician, patient or room. Intervals are half open: touching is legal."""

from datetime import timedelta

import pytest
from django.db import DatabaseError, transaction
from django.db.models import Model

from scheduling.models.builders import STARTS_AT, field_of, make, model_class, refuses

pytestmark = pytest.mark.django_db

TEN_FIFTEEN = STARTS_AT + timedelta(minutes=15)
TEN_THIRTY = STARTS_AT + timedelta(minutes=30)
TEN_FORTY_FIVE = STARTS_AT + timedelta(minutes=45)
ELEVEN = STARTS_AT + timedelta(hours=1)
SHARED = ["clinician", "patient", "room"]
ACTIVE_STATUSES = ["BOOKED", "CONFIRMED", "CHECKED_IN", "COMPLETED"]
BLOCKS_NOTHING = [
    ("CANCELLED", {"cancelled_at": STARTS_AT, "cancellation_reason": "moved"}),
    ("NO_SHOW", {}),
]


def _shared_resource(dimension: str) -> dict[str, Model]:
    names = {"clinician": "ClinicianProfile", "patient": "User", "room": "Room"}
    return {dimension: make(names[dimension])}


def _first_appointment(dimension: str, **overrides: object) -> dict[str, Model]:
    shared = _shared_resource(dimension)
    make("Appointment", starts_at=STARTS_AT, ends_at=TEN_THIRTY, **shared, **overrides)
    return shared


@pytest.mark.parametrize("dimension", SHARED)
def rejects_appointment_when_active_one_overlaps_for_the_same_resource(dimension: str) -> None:
    shared = _first_appointment(dimension)

    refuses("Appointment", starts_at=TEN_FIFTEEN, ends_at=TEN_FORTY_FIVE, **shared)


@pytest.mark.parametrize("dimension", SHARED)
def rejects_appointment_when_interval_is_identical_for_the_same_resource(dimension: str) -> None:
    shared = _first_appointment(dimension)

    refuses("Appointment", starts_at=STARTS_AT, ends_at=TEN_THIRTY, **shared)


@pytest.mark.parametrize("dimension", SHARED)
def rejects_appointment_when_it_lies_inside_an_active_one(dimension: str) -> None:
    shared = _first_appointment(dimension)

    refuses(
        "Appointment",
        starts_at=STARTS_AT + timedelta(minutes=5),
        ends_at=STARTS_AT + timedelta(minutes=10),
        **shared,
    )


@pytest.mark.parametrize("status", ACTIVE_STATUSES)
def rejects_appointment_when_overlapping_one_has_an_active_status(status: str) -> None:
    shared = _first_appointment("clinician", status=status)

    refuses("Appointment", starts_at=TEN_FIFTEEN, ends_at=TEN_FORTY_FIVE, **shared)


@pytest.mark.parametrize("dimension", SHARED)
def returns_appointment_when_it_starts_where_the_other_ends(dimension: str) -> None:
    shared = _first_appointment(dimension)

    later = make("Appointment", starts_at=TEN_THIRTY, ends_at=ELEVEN, **shared)

    assert model_class("Appointment")._default_manager.filter(pk=later.pk).exists()


@pytest.mark.parametrize("dimension", SHARED)
def returns_appointment_when_it_ends_where_the_other_starts(dimension: str) -> None:
    shared = _first_appointment(dimension)

    earlier = make(
        "Appointment", starts_at=STARTS_AT - timedelta(minutes=30), ends_at=STARTS_AT, **shared
    )

    assert model_class("Appointment")._default_manager.filter(pk=earlier.pk).exists()


@pytest.mark.parametrize(("status", "extra"), BLOCKS_NOTHING)
@pytest.mark.parametrize("dimension", SHARED)
def returns_appointment_when_overlapping_one_blocks_nothing(
    dimension: str, status: str, extra: dict[str, object]
) -> None:
    shared = _first_appointment(dimension, status=status, **extra)

    overlapping = make("Appointment", starts_at=TEN_FIFTEEN, ends_at=TEN_FORTY_FIVE, **shared)

    assert model_class("Appointment")._default_manager.filter(pk=overlapping.pk).exists()


@pytest.mark.parametrize("dimension", SHARED)
def returns_appointment_when_overlap_is_with_a_different_resource(dimension: str) -> None:
    _first_appointment(dimension)

    other = make("Appointment", starts_at=TEN_FIFTEEN, ends_at=TEN_FORTY_FIVE)

    assert model_class("Appointment")._default_manager.count() == 2
    assert other.pk is not None


def returns_appointment_when_two_overlapping_ones_have_no_room() -> None:
    make("Appointment", starts_at=STARTS_AT, ends_at=TEN_THIRTY, room=None)

    second = make("Appointment", starts_at=TEN_FIFTEEN, ends_at=TEN_FORTY_FIVE, room=None)

    assert (
        field_of(model_class("Appointment")._default_manager.get(pk=second.pk), "room_id") is None
    )


def rejects_update_when_cancelled_appointment_is_reactivated_into_an_overlap() -> None:
    clinician = make("ClinicianProfile")
    make("Appointment", clinician=clinician, starts_at=STARTS_AT, ends_at=TEN_THIRTY)
    cancelled = make(
        "Appointment",
        clinician=clinician,
        starts_at=TEN_FIFTEEN,
        ends_at=TEN_FORTY_FIVE,
        status="CANCELLED",
        cancelled_at=STARTS_AT,
        cancellation_reason="moved",
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        model_class("Appointment")._default_manager.filter(pk=cancelled.pk).update(
            status="BOOKED", cancelled_at=None, cancellation_reason=""
        )
