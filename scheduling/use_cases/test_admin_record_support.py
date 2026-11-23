"""Shared set-up of the admin record use case tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import Model

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Department, Hospital, User
from scheduling.models.builders import make
from scheduling.use_cases.request_context import bind_request_context

if TYPE_CHECKING:
    from scheduling.use_cases.admin_records import RecordEdit

NOW = datetime(2030, 3, 15, 9, 0, tzinfo=UTC)
CONTEXT = RequestContext(correlation_id="corr-admin", now=NOW)
KINDS = ("hospital", "specialty", "department", "room", "appointment_type")
MODEL_OF = {
    "hospital": "Hospital",
    "specialty": "Specialty",
    "department": "Department",
    "room": "Room",
    "appointment_type": "AppointmentType",
}


def _an_admin() -> User:
    user = make("User", role="ADMIN")
    assert isinstance(user, User)
    return user


def _a_department() -> Department:
    department = make("Department")
    assert isinstance(department, Department)
    return department


def _a_hospital() -> Hospital:
    hospital = make("Hospital")
    assert isinstance(hospital, Hospital)
    return hospital


def _hospital_values(**overrides: object) -> dict[str, object]:
    return {
        "name": "Saint Anne",
        "code": "saint-anne",
        "description": "",
        "street_address": "1 Rue Neuve",
        "postal_code": "75001",
        "city": "Paris",
        "country": "France",
        "phone": "+33 1 23 45 67 89",
        "time_zone": "Europe/Paris",
        "latitude": None,
        "longitude": None,
        "is_active": True,
        **overrides,
    }


def _values_for(kind: str, **overrides: object) -> dict[str, object]:
    """Valid values of a new record of the kind, with its parent made when it needs one."""
    base: dict[str, dict[str, object]] = {
        "hospital": _hospital_values(),
        "specialty": {"name": "Neurology", "code": "neurology", "is_active": True},
        "department": {"name": "Imaging", "code": "imaging", "description": ""},
        "room": {
            "name": "Room 7", "code": "room-7", "floor": "2", "capacity": 2,
            "equipment": ["scanner"], "is_active": True,
        },
        "appointment_type": {
            "name": "Scan", "code": "scan", "duration_minutes": 20, "needs_room": True,
            "buffer_minutes": 5, "colour": "#1a2b3c", "is_active": True,
            "is_bookable_online": True,
        },
    }  # fmt: skip
    values = base[kind]
    if kind == "department":
        values = {**values, "hospital_id": _a_hospital().pk}
    if kind in ("room", "appointment_type"):
        values = {**values, "department_id": _a_department().pk}
    return {**values, **overrides}


def _make_existing(kind: str, **overrides: object) -> Model:
    return make(MODEL_OF[kind], **overrides)


def _created(kind: str, actor: User, **overrides: object) -> UUID:
    result = _in_context(lambda: _create(kind, _values_for(kind, **overrides), actor))
    assert isinstance(result, Success), result
    return result.value


def _an_edit(kind: str, record_id: UUID, values: dict[str, object], version: int) -> "RecordEdit":
    from scheduling.use_cases.admin_records import RecordEdit

    return RecordEdit(kind, record_id, values, version)


def _create(kind: str, values: dict[str, object], actor: User) -> Result[UUID]:
    from scheduling.use_cases.admin_records import create_record

    return create_record(kind, values, actor)


def _delete(kind: str, record_id: UUID, actor: User) -> Result[None]:
    from scheduling.use_cases.admin_records import delete_record

    return delete_record(kind, record_id, actor)


def _edited(edit: "RecordEdit", actor: User) -> Result[UUID]:
    from scheduling.use_cases.admin_records import update_record

    return _in_context(lambda: update_record(edit, actor))


def _in_context[Value](action: Callable[[], Value]) -> Value:
    with bind_request_context(CONTEXT):
        return action()


def _field_messages(result: object) -> list[FieldMessage]:
    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT, result
    fields = result.details["fields"]
    assert isinstance(fields, list)
    return [FieldMessage(item["field"], item["message"]) for item in fields]
