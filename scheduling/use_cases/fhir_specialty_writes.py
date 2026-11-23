"""Writes the whole specialty list as one CodeSystem, spec 15.4. Each change
goes through the console's use cases, so checks and audit entries are the console's; one
transaction, and the first refusal undoes every change before it."""

from django.db import connection, transaction

from scheduling.domain.failure import Failure, FailureCode, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_specialty_write import (
    ROOT,
    Change,
    StoredConcept,
    desired_concepts,
    plan_changes,
)
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.models import Specialty, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.admin_records import (
    RecordEdit,
    create_record,
    delete_record,
    update_record,
)
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.fhir_record_writes import admin_of

SPECIALTY_KIND = "specialty"
LIST_LOCK_KEY = 2_024_002
ELEMENT_OF_FIELD = {"name": "display", "code": "code"}


def specialty_write_refusal(caller: Caller) -> Failure | None:
    admin = admin_of(caller)
    return admin if isinstance(admin, Failure) else None


def update_specialty_list(
    body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    admin = admin_of(caller)
    if isinstance(admin, Failure):
        return admin
    desired = desired_concepts(body)
    if isinstance(desired, str):
        return Failure.invalid_input([FieldMessage(desired, "This element is not valid.")])
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LIST_LOCK_KEY])
        if expected_version not in (None, loading.specialty_revision()):
            return stale_version()
        stored = tuple(
            StoredConcept(row.pk, row.code, row.name, row.is_active)
            for row in Specialty.objects.order_by("code")
        )
        for change in (item for group in plan_changes(stored, desired) for item in group):
            refused = _applied(change, admin)
            if refused is not None:
                transaction.set_rollback(True)
                return refused
        return Success(loading.specialty_code_system_resource(include_inactive=True))


def _applied(change: Change, admin: User) -> Failure | None:
    """None when the console accepted the change, else its refusal in the client's terms."""
    concept, row = change.concept, change.stored
    if concept is None:
        if row is None:
            return None
        removed = delete_record(SPECIALTY_KIND, row.key, admin)
        return removed if isinstance(removed, Failure) else None
    values: dict[str, object] = {"name": concept.display, "is_active": not concept.inactive}
    if row is None:
        saved = create_record(SPECIALTY_KIND, {**values, "code": concept.code}, admin)
    else:
        saved = update_record(RecordEdit(SPECIALTY_KIND, row.key, values, None), admin)
    return _named(saved, concept.index) if isinstance(saved, Failure) else None


def _named(failure: Failure, index: int) -> Failure:
    """The console names form fields; a FHIR client is told the element of its own body."""
    raw = failure.details.get("fields")
    if failure.code is not FailureCode.INVALID_INPUT or not isinstance(raw, list):
        return failure
    return Failure.invalid_input(
        [
            FieldMessage(
                f"{ROOT}.concept[{index}].{ELEMENT_OF_FIELD.get(str(item['field']), 'code')}",
                str(item["message"]),
            )
            for item in raw
            if isinstance(item, dict)
        ]
    )
