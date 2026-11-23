"""Section 5.2: step 5, "Types that need no room get none", for a staff booking
that names a room."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scheduling.models import Appointment
from scheduling.models.builders import Clinic, add_clinician, make, make_clinic
from scheduling.views import clock
from scheduling.views.test_appointment_support import APPOINTMENTS, _admin, _signed_in

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
START = "2030-01-14T10:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _staff_booking(
    clinic: Clinic, room_id: object, type_id: object | None = None
) -> dict[str, object]:
    return {
        "appointment_type_id": str(type_id or clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "patient_id": str(clinic.patient.pk),
        "starts_at": START,
        "room_id": str(room_id),
    }


def returns_no_room_when_staff_book_a_type_needing_none_and_name_a_room() -> None:
    clinic = make_clinic(type_fields={"needs_room": False})
    room = make("Room", department=clinic.department)

    response = _signed_in(_admin()).post(
        APPOINTMENTS, _staff_booking(clinic, room.pk), content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["room_id"] is None
    assert Appointment.objects.get().room_id is None


def returns_201_for_a_room_type_after_a_no_room_booking_named_the_same_room() -> None:
    clinic = make_clinic(type_fields={"needs_room": False})
    room = make("Room", department=clinic.department)
    room_type = make("AppointmentType", department=clinic.department, needs_room=True)
    other = add_clinician(clinic.department)
    client = _signed_in(_admin())
    client.post(APPOINTMENTS, _staff_booking(clinic, room.pk), content_type="application/json")
    second = {
        **_staff_booking(clinic, room.pk, room_type.pk),
        "clinician_id": str(other.pk),
        "patient_id": str(make("User").pk),
    }

    response = client.post(APPOINTMENTS, second, content_type="application/json")

    assert response.status_code == 201


def returns_201_for_a_no_room_type_naming_a_room_another_appointment_holds() -> None:
    clinic = make_clinic(type_fields={"needs_room": False})
    room = make("Room", department=clinic.department)
    room_type = make("AppointmentType", department=clinic.department, needs_room=True)
    other = add_clinician(clinic.department)
    client = _signed_in(_admin())
    holder = {
        **_staff_booking(clinic, room.pk, room_type.pk),
        "clinician_id": str(other.pk),
        "patient_id": str(make("User").pk),
    }
    assert client.post(APPOINTMENTS, holder, content_type="application/json").status_code == 201

    response = client.post(
        APPOINTMENTS, _staff_booking(clinic, room.pk), content_type="application/json"
    )

    assert response.status_code == 201
    assert response.json()["room_id"] is None
