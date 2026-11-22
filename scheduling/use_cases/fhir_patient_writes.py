"""Task 23, spec 15.1, 15.4, 15.5: Patient update. A patient changes phone and birth date by the
profile page rules; an admin name, email and active as the console does. Any other element
that differs from the stored record is refused and named."""

from uuid import UUID

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_patient import (
    ADMIN_MAY_CHANGE,
    PATIENT_MAY_CHANGE,
    patient_values,
    refused_changes,
)
from scheduling.domain.vocabulary import Role
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_users import update_user
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_patient_reads import read_patient
from scheduling.use_cases.profile import ProfileCommand, update_profile

REFUSED_MESSAGE = "This element cannot be changed by this caller."
UNREADABLE_MESSAGE = "This element cannot be read."


def update_patient(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    user = caller.user
    if user is None:
        return Failure.unauthenticated()
    if caller.role not in (Role.ADMIN, Role.PATIENT):
        return Failure.forbidden()
    stored = read_patient(str(identifier), caller)
    if isinstance(stored, Failure):
        return stored
    allowed = ADMIN_MAY_CHANGE if caller.role is Role.ADMIN else PATIENT_MAY_CHANGE
    refused = refused_changes(stored.value, body, allowed)
    if refused:
        return Failure.invalid_input([FieldMessage(name, REFUSED_MESSAGE) for name in refused])
    values = patient_values(body)
    if isinstance(values, str):
        return Failure.invalid_input([FieldMessage(values, UNREADABLE_MESSAGE)])
    if caller.role is Role.ADMIN:
        version = _stored_version(stored.value)
        edit = RecordEdit(
            "user",
            identifier,
            {"full_name": values.full_name, "email": values.email, "is_active": values.is_active},
            version,
        )
        failure = _failure_of(update_user(edit, user, expected_version))
    else:
        command = ProfileCommand(values.phone, values.birth_date)
        failure = _failure_of(update_profile(command, user, expected_version))
    if failure is not None:
        return _named_by_fhir_path(failure)
    return Success(loading.patients([identifier])[0])


def _failure_of[Value](written: Result[Value]) -> Failure | None:
    return written if isinstance(written, Failure) else None


def _stored_version(stored: Resource) -> int:
    meta_block = stored["meta"]
    return int(str(meta_block["versionId"])) if isinstance(meta_block, dict) else 0


FHIR_PATH_OF_FIELD = {
    "phone": "Patient.telecom",
    "email": "Patient.telecom",
    "date_of_birth": "Patient.birthDate",
    "full_name": "Patient.name",
    "is_active": "Patient.active",
}


def _named_by_fhir_path(failure: Failure) -> Failure:
    """The use cases name form fields; a FHIR client is told the element of its own body."""
    raw = failure.details.get("fields")
    if failure.code is not FailureCode.INVALID_INPUT or not isinstance(raw, list):
        return failure
    return Failure.invalid_input(
        [
            FieldMessage(
                FHIR_PATH_OF_FIELD.get(str(item["field"]), str(item["field"])), str(item["message"])
            )
            for item in raw
            if isinstance(item, dict)
        ]
    )
