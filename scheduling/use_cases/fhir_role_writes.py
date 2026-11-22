"""Task 24c, spec 15.2 and 15.4: PractitionerRole writes. An admin writes a profile through the
console's use cases; a clinician records and removes the own time off through theirs. Their
checks, refusals, audit entries and versions apply."""

from uuid import UUID

from django.db import transaction

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_role_write import (
    ADMIN_FREE,
    CREATE_FREE,
    NOT_AVAILABLE,
    OWN_FREE,
    TimeOffChanges,
    role_difference,
    role_values,
    time_off_changes,
)
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import Role
from scheduling.models import ClinicianProfile, Specialty, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.admin_clinicians import attach_profile, delete_profile, update_profile
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_record_writes import DERIVED_MESSAGE, admin_of, named
from scheduling.use_cases.time_off import TimeOffCommand, create_time_off, delete_time_off

KIND = "clinician"
SPECIALTY_ELEMENT = "PractitionerRole.specialty"
NOT_AVAILABLE_MESSAGE = "Time off is recorded and removed, not edited."


def role_write_refusal(method: str, caller: Caller) -> Failure | None:
    """Asked before the body is read: an admin may write, a clinician may only `PUT`."""
    if caller.user is None:
        return Failure.unauthenticated()
    if caller.role is Role.ADMIN or (caller.role is Role.CLINICIAN and method == "PUT"):
        return None
    return Failure.forbidden()


def create_role(body: dict[str, object], caller: Caller) -> Result[Resource]:
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    problem = role_difference(body, {}, CREATE_FREE)
    if problem:
        return _invalid(problem, DERIVED_MESSAGE)
    values = _console_values(body)
    if isinstance(values, Failure):
        return values
    created = attach_profile(values, admin)
    if isinstance(created, Failure):
        return named(created, KIND)
    return Success(_role(created.value))


def update_role(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    if caller.user is None:
        return Failure.unauthenticated()
    if caller.role is Role.ADMIN:
        return _admin_update(identifier, body, caller.user, expected_version)
    if caller.role is Role.CLINICIAN:
        return _own_update(identifier, body, caller.user, expected_version)
    return Failure.forbidden()


def delete_role(identifier: UUID, caller: Caller, expected_version: int | None) -> Result[None]:
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    return delete_profile(identifier, admin, expected_version)


def _admin_update(
    identifier: UUID, body: dict[str, object], admin: User, expected_version: int | None
) -> Result[Resource]:
    profile = ClinicianProfile.objects.filter(pk=identifier).first()
    if profile is None:
        return Failure.not_found()
    stored = _role(identifier)
    problem = role_difference(body, stored, ADMIN_FREE)
    if problem:
        return _invalid(problem, DERIVED_MESSAGE)
    changes = time_off_changes(body, stored)
    if isinstance(changes, str) or not changes.is_empty:
        return _invalid(NOT_AVAILABLE, "An admin cannot record or remove time off.")
    values = _console_values(body)
    if isinstance(values, Failure):
        return values
    edit = RecordEdit(KIND, identifier, values, profile.version)
    updated = update_profile(edit, admin, expected_version)
    if isinstance(updated, Failure):
        return named(updated, KIND)
    return Success(_role(identifier))


def _own_update(
    identifier: UUID, body: dict[str, object], clinician: User, expected_version: int | None
) -> Result[Resource]:
    with transaction.atomic():
        profile = ClinicianProfile.objects.select_for_update().filter(pk=identifier).first()
        if profile is None:
            return Failure.not_found()
        if profile.user_id != clinician.pk:
            return Failure.forbidden()
        if expected_version not in (None, profile.version):
            return stale_version()
        stored = _role(identifier)
        problem = role_difference(body, stored, OWN_FREE)
        if problem:
            return _invalid(problem, DERIVED_MESSAGE)
        changes = time_off_changes(body, stored)
        if isinstance(changes, str):
            return _invalid(changes, NOT_AVAILABLE_MESSAGE)
        failure = _apply(changes, clinician)
        if failure is not None:
            transaction.set_rollback(True)
            return failure
    return Success(_role(identifier))


def _apply(changes: TimeOffChanges, clinician: User) -> Failure | None:
    for removed_id in changes.removed_ids:
        removed = delete_time_off(UUID(removed_id), clinician)
        if isinstance(removed, Failure):
            return removed
    for addition in changes.additions:
        command = TimeOffCommand(addition.starts_at, addition.ends_at, addition.reason)
        recorded = create_time_off(command, clinician)
        if isinstance(recorded, Failure):
            return _as_not_available(recorded)
    return None


def _console_values(body: dict[str, object]) -> dict[str, object] | Failure:
    """The console's profile fields: the specialty code of the body becomes the row's id."""
    values = role_values(body)
    if isinstance(values, str):
        return _invalid(values)
    code = values.pop("specialty_code")
    specialty_id = Specialty.objects.filter(code=code).values_list("pk", flat=True).first()
    if specialty_id is None:
        return _invalid(SPECIALTY_ELEMENT, "No specialty has this code.")
    return {**values, "specialty_id": specialty_id}


def _role(identifier: UUID) -> Resource:
    return loading.practitioner_roles_with_all_services([identifier])[0]


def _invalid(element: str, message: str = "This element is not valid.") -> Failure:
    return Failure.invalid_input([FieldMessage(element, message)])


def _as_not_available(failure: Failure) -> Failure:
    """The console names the form fields of a period; a client is told its element."""
    raw = failure.details.get("fields")
    if not isinstance(raw, list):
        return failure
    messages = [str(item["message"]) for item in raw if isinstance(item, dict)]
    return Failure.invalid_input([FieldMessage(NOT_AVAILABLE, text) for text in messages])
