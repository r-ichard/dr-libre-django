"""Section 5.2 lock order (clinicians by id, patient, rooms by id) and what a placement refuses to
swallow. The order guards against deadlock, so it is asserted on the lock statements."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, User
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LOCK_CLAUSE = "FOR NO KEY UPDATE"


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-lock", NOW)):
        yield


def _admin() -> User:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    return admin


def _command(clinic: Clinic, room_id: object = None) -> PlacementCommand:
    return PlacementCommand(
        clinic.appointment_type.pk,
        STARTS_AT,
        clinic.clinician.pk,
        clinic.patient.pk,
        room_id,  # type: ignore[arg-type]
    )


def _lock_statements(clinic: Clinic) -> list[str]:
    with CaptureQueriesContext(connection) as captured:
        place_appointment(_command(clinic), _admin())
    return [query["sql"] for query in captured if LOCK_CLAUSE in query["sql"]]


def returns_locks_on_clinicians_then_patient_then_rooms_when_type_needs_room() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    make("Room", department=clinic.department)

    locked = _lock_statements(clinic)

    tables = [
        next(
            name
            for name in ("clinicianprofile", "room", "user")
            if f'FROM "scheduling_{name}"' in sql
        )
        for sql in locked
    ]
    assert tables == ["clinicianprofile", "user", "room"]


def returns_ascending_id_order_on_every_lock_when_booking() -> None:
    clinic = make_clinic(type_fields={"needs_room": True})
    make("Room", department=clinic.department)

    locked = _lock_statements(clinic)

    for sql in (
        statement for statement in locked if "clinicianprofile" in statement or "room" in statement
    ):
        assert "ORDER BY" in sql
        assert "DESC" not in sql


def returns_no_room_lock_when_type_needs_no_room() -> None:
    clinic = make_clinic()
    make("Room", department=clinic.department)

    locked = _lock_statements(clinic)

    assert not any('FROM "scheduling_room"' in sql for sql in locked)


def returns_room_in_audit_ids_when_a_room_is_booked() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department)

    result = place_appointment(_command(clinic, room.pk), _admin())

    assert isinstance(result, Success)
    entry = AuditLogEntry.objects.get(action="appointment.book")
    assert entry.metadata["ids"]["room_id"] == str(room.pk)


def raises_when_integrity_error_is_not_an_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    clinic = make_clinic()

    def refuse(**fields: object) -> Appointment:
        raise IntegrityError("some other constraint")

    monkeypatch.setattr(Appointment.objects, "create", refuse)

    with pytest.raises(IntegrityError):
        place_appointment(_command(clinic), _admin())
