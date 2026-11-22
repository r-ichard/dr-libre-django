"""Task 18, item 8: what the public search and the booking pages offer follows the admin records
at once, through the same loading. Admin edits go through the use case, reads through HTTP."""

from datetime import UTC, datetime, time
from uuid import UUID

import pytest

from scheduling.models import AppointmentType, Hospital, Room, Specialty
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.use_cases.test_admin_record_support import (
    _an_admin,
    _an_edit,
    _create,
    _edited,
    _in_context,
    _values_for,
)
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
MONDAY = "from=2030-01-07T00:00:00Z&to=2030-01-08T00:00:00Z"


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _total(kind: str) -> int:
    total = browser_api_client().get(f"/api/v1/search/{kind}").json()["total"]
    assert isinstance(total, int)
    return total


def _deactivate(kind: str, record_id: UUID, version: int) -> None:
    _edited(_an_edit(kind, record_id, {"is_active": False}, version), _an_admin())


def _slot_count(clinic: Clinic) -> int:
    query = f"appointment_type_id={clinic.appointment_type.pk}&{MONDAY}"
    response = browser_api_client().get(f"/api/v1/slots?{query}")
    return len(response.json()["slots"]) if response.status_code == 200 else 0


def returns_no_provider_and_no_hospital_when_hospital_is_deactivated() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    hospital = Hospital.objects.get(pk=clinic.department.hospital_id)
    assert (_total("providers"), _total("hospitals")) == (1, 1)

    _deactivate("hospital", hospital.pk, hospital.version)

    assert (_total("providers"), _total("hospitals")) == (0, 0)


def returns_no_provider_and_no_specialty_when_specialty_is_deactivated() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    specialty = Specialty.objects.get(pk=clinic.clinician.specialty_id)
    assert (_total("providers"), _total("specialties")) == (1, 1)

    _deactivate("specialty", specialty.pk, specialty.version)

    assert (_total("providers"), _total("specialties")) == (0, 0)


def returns_no_slots_when_appointment_type_is_deactivated() -> None:
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    assert _slot_count(clinic) == 2

    _deactivate("appointment_type", clinic.appointment_type.pk, clinic.appointment_type.version)

    assert _slot_count(clinic) == 0


def returns_no_slots_when_the_only_room_is_deactivated() -> None:
    clinic = make_clinic(type_fields={"needs_room": True}, rule_fields=HOUR_OF_SLOTS)
    room = make("Room", department=clinic.department)
    assert isinstance(room, Room)
    assert _slot_count(clinic) == 2

    _deactivate("room", room.pk, room.version)

    assert _slot_count(clinic) == 0


def returns_the_new_type_on_the_booking_page_when_its_department_has_an_available_clinician() -> (
    None
):
    clinic = make_clinic(rule_fields=HOUR_OF_SLOTS)
    values = _values_for("appointment_type", department_id=clinic.department.pk, code="new-type")

    _in_context(lambda: _create("appointment_type", values, _an_admin()))

    new_type = AppointmentType.objects.get(code="new-type")
    page = browser_api_client().get("/book").content.decode()
    assert str(new_type.pk) in page
