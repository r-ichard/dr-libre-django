"""Spec 15.4: Practitioner update and delete. An admin's write does what the console does
for a user (`update_user`, `deactivate_user`, `update_profile`, `delete_user`), with the
same rules and audit entries; one transaction holds every step of a `PUT`."""

from uuid import UUID

from django.db import transaction

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_practitioner import (
    PractitionerValues,
    practitioner_values,
    refused_practitioner_changes,
)
from scheduling.domain.fhir_search import parse_id
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.models import ClinicianProfile, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.admin_clinicians import update_profile
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_user_support import lock_users
from scheduling.use_cases.admin_users import deactivate_user, delete_user, update_user
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_record_writes import admin_of

REFUSED_MESSAGE = "This element cannot be changed through this resource."
UNREADABLE_MESSAGE = "This element cannot be read."
ELEMENT_OF_FIELD = {
    "full_name": "Practitioner.name",
    "email": "Practitioner.telecom",
    "is_active": "Practitioner.active",
    "title": "Practitioner.qualification",
}
ACTIVE_ELEMENT = "Practitioner.active"


def practitioner_write_refusal(raw_identifier: str | None, caller: Caller) -> Failure | None:
    """Asked before the body is read: only an admin writes, and a user without a profile is not
    a Practitioner, so there is nothing to describe."""
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    identifier = parse_id(raw_identifier) if raw_identifier is not None else None
    if identifier is None or not ClinicianProfile.objects.filter(user_id=identifier).exists():
        return Failure.not_found()
    return None


def update_practitioner(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    stored = loading.practitioners_with_contact([identifier])
    if not stored:
        return Failure.not_found()
    refused = refused_practitioner_changes(stored[0], body)
    if refused:
        return Failure.invalid_input(
            [FieldMessage(element, REFUSED_MESSAGE) for element in refused]
        )
    values = practitioner_values(body, stored[0])
    if isinstance(values, str):
        return Failure.invalid_input([FieldMessage(values, UNREADABLE_MESSAGE)])
    with transaction.atomic():
        failure = _apply(identifier, values, admin, expected_version)
        if failure is not None:
            transaction.set_rollback(True)
            return failure
    return Success(loading.practitioners_with_contact([identifier])[0])


def delete_practitioner(
    identifier: UUID, caller: Caller, expected_version: int | None
) -> Result[None]:
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    return delete_user(identifier, admin, expected_version)


def _apply(
    identifier: UUID, values: PractitionerValues, admin: User, expected_version: int | None
) -> Failure | None:
    locked = lock_users(admin.pk, identifier)
    target = locked.target
    if locked.admin is None:
        return Failure.forbidden()
    if target is None:
        return Failure.not_found()
    if expected_version not in (None, target.version):
        return stale_version()
    fields = {
        "full_name": values.full_name,
        "email": values.email,
        "is_active": values.is_active or target.is_active,
    }
    failure = _failure_of(
        update_user(RecordEdit("user", identifier, fields, target.version), admin)
    )
    if failure is None and values.title is not None:
        failure = _update_title(identifier, values.title, admin)
    if failure is None and not values.is_active and target.is_active:
        version = User.objects.values_list("version", flat=True).get(pk=identifier)
        failure = _failure_of(deactivate_user(identifier, version, admin))
    return None if failure is None else _named(failure)


def _update_title(identifier: UUID, title: str, admin: User) -> Failure | None:
    profile = ClinicianProfile.objects.get(user_id=identifier)
    edit = RecordEdit("clinician", profile.pk, {"title": title}, profile.version)
    return _failure_of(update_profile(edit, admin))


def _failure_of[Value](written: Result[Value]) -> Failure | None:
    return written if isinstance(written, Failure) else None


def _named(failure: Failure) -> Failure:
    """The console names form fields and rules; a client is told the element of its own body."""
    if failure.code is FailureCode.RULE_VIOLATION:
        rules = failure.details.get("violated_rules")
        reasons = rules if isinstance(rules, list) else []
        return Failure.invalid_input([FieldMessage(ACTIVE_ELEMENT, str(item)) for item in reasons])
    raw = failure.details.get("fields")
    if failure.code is not FailureCode.INVALID_INPUT or not isinstance(raw, list):
        return failure
    return Failure.invalid_input(
        [
            FieldMessage(
                ELEMENT_OF_FIELD.get(str(item["field"]), str(item["field"])), str(item["message"])
            )
            for item in raw
            if isinstance(item, dict)
        ]
    )
