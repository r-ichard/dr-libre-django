"""Section 5.2 steps 3 and 4: which appointments overlap, and which resource a constraint names."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases import placement_checks
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
THIRTY_MINUTES = timedelta(minutes=30)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-overlap", NOW)):
        yield


def _book(clinic: Clinic, room_id: object = None) -> Success[Appointment] | Failure:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    command = PlacementCommand(
        clinic.appointment_type.pk,
        STARTS_AT,
        clinic.clinician.pk,
        clinic.patient.pk,
        room_id,  # type: ignore[arg-type]
    )
    return place_appointment(command, admin)


def _existing(clinic: Clinic, starts_at: datetime, **overrides: object) -> None:
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + THIRTY_MINUTES,
        **overrides,
    )


def _cancelled() -> dict[str, object]:
    return {"status": "CANCELLED", "cancelled_at": NOW, "cancellation_reason": "Patient asked"}


def returns_booking_when_the_other_appointment_ends_exactly_at_the_start() -> None:
    clinic = make_clinic()
    _existing(
        clinic, STARTS_AT - THIRTY_MINUTES, clinician=clinic.clinician, patient=clinic.patient
    )

    assert isinstance(_book(clinic), Success)


def returns_booking_when_the_other_appointment_starts_exactly_at_the_end() -> None:
    clinic = make_clinic()
    _existing(
        clinic, STARTS_AT + THIRTY_MINUTES, clinician=clinic.clinician, patient=clinic.patient
    )

    assert isinstance(_book(clinic), Success)


def returns_booking_when_the_overlapping_appointment_is_cancelled() -> None:
    clinic = make_clinic()
    _existing(clinic, STARTS_AT, clinician=clinic.clinician, **_cancelled())

    assert isinstance(_book(clinic), Success)


def returns_the_room_when_its_only_appointment_is_cancelled() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    room = make("Room", department=clinic.department)
    other = add_clinician(clinic.department)
    _existing(clinic, STARTS_AT, room=room, clinician=other, **_cancelled())

    result = _book(clinic)

    assert isinstance(result, Success)
    assert result.value.room_id == room.pk


def returns_conflict_naming_patient_when_only_the_constraint_catches_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = make_clinic()
    _existing(clinic, STARTS_AT, patient=clinic.patient, clinician=add_clinician(clinic.department))
    _stale_checks(monkeypatch)

    assert _book(clinic) == Failure.conflict(["patient"])


def returns_conflict_naming_room_when_only_the_constraint_catches_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department)
    _existing(clinic, STARTS_AT, room=room, clinician=add_clinician(clinic.department))
    _stale_checks(monkeypatch)

    assert _book(clinic, room.pk) == Failure.conflict(["room"])


def _stale_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(placement_checks, "find_conflicts", lambda *_arguments: [])
    monkeypatch.setattr(placement_checks, "violated_booking_rules", lambda *_arguments: [])


def returns_the_room_when_its_other_appointment_ends_exactly_at_the_start() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    room = make("Room", department=clinic.department)
    other = add_clinician(clinic.department)
    _existing(clinic, STARTS_AT - THIRTY_MINUTES, room=room, clinician=other)

    result = _book(clinic)

    assert isinstance(result, Success)
    assert result.value.room_id == room.pk
