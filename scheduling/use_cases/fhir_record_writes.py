"""Task 24b, spec 15.4: FHIR admin writes for a department, a hospital site, a room and an
appointment type. Each goes through the console's use cases in `admin_records`, so checks,
refusals, audit entry and version are the console's."""

from collections.abc import Callable
from uuid import UUID

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_record_write import (
    ELEMENT_OF_FIELD,
    VALUES_OF,
    derived_difference,
    location_kind,
)
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import Role
from scheduling.models import Hospital, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.admin_records import (
    RecordEdit,
    create_record,
    delete_record,
    update_record,
)
from scheduling.use_cases.fhir_caller import Caller

DERIVED_MESSAGE = "This element is built by the server and cannot be changed."
RECORD_TYPES = ("Organization", "Location", "HealthcareService")
KIND_OF_TYPE = {"Organization": "department", "HealthcareService": "appointment_type"}
LOADERS: dict[str, Callable[[list[UUID]], list[Resource]]] = {
    "hospital": loading.site_locations,
    "department": loading.department_organizations,
    "room": loading.room_locations,
    "appointment_type": loading.healthcare_services,
}


def is_hospital_organization(resource_type: str, identifier: UUID) -> bool:
    """A hospital is written as its site Location; its Organization is read-only."""
    return resource_type == "Organization" and Hospital.objects.filter(pk=identifier).exists()


def write_refusal(resource_type: str, caller: Caller) -> Failure | None:
    """Asked before the body is read, so a caller who may not write learns that, not what is wrong
    with a body they had no right to send."""
    if resource_type not in RECORD_TYPES:
        return None
    admin = _admin(caller)
    return admin if isinstance(admin, Failure) else None


def create_record_resource(
    resource_type: str, body: dict[str, object], caller: Caller
) -> Result[Resource]:
    admin = _admin(caller)
    if isinstance(admin, Failure):
        return admin
    kind = location_kind(body) if resource_type == "Location" else KIND_OF_TYPE[resource_type]
    if kind is None:
        return _invalid("Location.physicalType")
    problem = derived_difference(body, {}, kind)
    if problem:
        return _invalid(f"{resource_type}.{problem}", DERIVED_MESSAGE)
    values = VALUES_OF[kind](body)
    if isinstance(values, str):
        return _invalid(values)
    created = create_record(kind, values, admin)
    if isinstance(created, Failure):
        return _named(created, kind)
    return Success(LOADERS[kind]([created.value])[0])


def update_record_resource(
    resource_type: str,
    identifier: UUID,
    body: dict[str, object],
    caller: Caller,
    expected_version: int | None,
) -> Result[Resource]:
    admin = _admin(caller)
    if isinstance(admin, Failure):
        return admin
    found = _stored(resource_type, identifier)
    if found is None:
        return Failure.not_found()
    kind, stored = found
    problem = derived_difference(body, stored, kind)
    if problem:
        return _invalid(f"{resource_type}.{problem}", DERIVED_MESSAGE)
    values = VALUES_OF[kind](body)
    if isinstance(values, str):
        return _invalid(values)
    edited = update_record(RecordEdit(kind, identifier, values, expected_version), admin)
    if isinstance(edited, Failure):
        return _named(edited, kind)
    return Success(LOADERS[kind]([identifier])[0])


def delete_record_resource(
    resource_type: str, identifier: UUID, caller: Caller, expected_version: int | None
) -> Result[None]:
    admin = _admin(caller)
    if isinstance(admin, Failure):
        return admin
    found = _stored(resource_type, identifier)
    if found is None:
        return Failure.not_found()
    return delete_record(found[0], identifier, admin, expected_version)


def _admin(caller: Caller) -> User | Failure:
    if caller.user is None:
        return Failure.unauthenticated()
    return caller.user if caller.role is Role.ADMIN else Failure.forbidden()


def _stored(resource_type: str, identifier: UUID) -> tuple[str, Resource] | None:
    """The kind of record the id belongs to under this type, and its resource."""
    kinds = ("hospital", "room") if resource_type == "Location" else (KIND_OF_TYPE[resource_type],)
    for kind in kinds:
        resources = LOADERS[kind]([identifier])
        if resources:
            return kind, resources[0]
    return None


def _invalid(element: str, message: str = "This element is not valid.") -> Failure:
    return Failure.invalid_input([FieldMessage(element, message)])


def _named(failure: Failure, kind: str) -> Failure:
    """The console names form fields and a stale record; a FHIR client is told the element of its
    own body and a stale `If-Match`."""
    if failure.code is FailureCode.CONFLICT and failure.details.get("resources") == [kind]:
        return stale_version()
    raw = failure.details.get("fields")
    if failure.code is not FailureCode.INVALID_INPUT or not isinstance(raw, list):
        return failure
    elements = ELEMENT_OF_FIELD[kind]
    return Failure.invalid_input(
        [
            FieldMessage(elements.get(str(item["field"]), str(item["field"])), str(item["message"]))
            for item in raw
            if isinstance(item, dict)
        ]
    )
