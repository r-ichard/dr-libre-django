"""Section 10: create, update and delete of the five admin records. One transaction per change:
lock, version, checks, save, audit. The admin comes from the session, never from the payload."""

from dataclasses import dataclass
from uuid import UUID
from zoneinfo import available_timezones

import psycopg.errors
from django.db import IntegrityError, transaction
from django.db.models import Model, ProtectedError

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.delete_dependents import delete_refusal
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.record_fields import check_code, check_colour, check_name, check_time_zone
from scheduling.domain.vocabulary import Role
from scheduling.models import ClinicianProfile, Room, User
from scheduling.models.base import Versioned
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.admin_record_specs import CODE_TAKEN, SPECS, RecordSpec, count_text
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit


@dataclass(frozen=True)
class RecordEdit:
    """What an admin saved: the record, the new values, and the version the form read. None is a
    write without `If-Match`: it applies to the current version."""

    kind: str
    record_id: UUID
    values: dict[str, object]
    version: int | None


def create_record(kind: str, values: dict[str, object], actor: User) -> Result[UUID]:
    spec = SPECS[kind]
    if not _is_admin(actor):
        return Failure.forbidden()
    with transaction.atomic():
        cleaned, messages = _cleaned(spec, values, creating=True)
        messages += _parent_and_code_messages(spec, cleaned, None)
        if messages:
            return Failure.invalid_input(messages)
        row = spec.model(**cleaned, created_by=actor)
        refused = _saved(spec, row)
        if refused is not None:
            return refused
        _audit(spec, "create", row, tuple(cleaned), actor)
        return Success(row.pk)


def update_record(edit: RecordEdit, actor: User) -> Result[UUID]:
    spec = SPECS[edit.kind]
    if not _is_admin(actor):
        return Failure.forbidden()
    with transaction.atomic():
        row = _locked(spec, edit.record_id)
        if row is None:
            return Failure.not_found()
        if edit.version is not None and row.version != edit.version:
            return Failure.conflict([edit.kind])
        cleaned, messages = _cleaned(spec, edit.values, creating=False)
        changed = {key: value for key, value in cleaned.items() if getattr(row, key) != value}
        messages += _parent_and_code_messages(spec, changed, row)
        messages += _room_move_messages(changed, row)
        if messages:
            return Failure.invalid_input(messages)
        if not changed:
            return Success(row.pk)
        for key, value in changed.items():
            setattr(row, key, value)
        refused = _saved(spec, row)
        if refused is not None:
            return refused
        _audit(spec, "update", row, tuple(changed), actor)
        return Success(row.pk)


def delete_record(
    kind: str, record_id: UUID, actor: User, expected_version: int | None = None
) -> Result[None]:
    spec = SPECS[kind]
    if not _is_admin(actor):
        return Failure.forbidden()
    with transaction.atomic():
        row = _locked(spec, record_id)
        if row is None:
            return Failure.not_found()
        if expected_version not in (None, row.version):
            return stale_version()
        blocked = dependents_of(kind, record_id)
        if blocked:
            return Failure.has_dependents(blocked)
        try:
            with transaction.atomic():
                row.delete()
        except (ProtectedError, IntegrityError):
            # A dependent committed after the count; it is a refusal, not an error.
            blocked = dependents_of(kind, record_id)
            if not blocked:
                raise
            return Failure.has_dependents(blocked)
        _audit(spec, "delete", row, (), actor, record_id)
        return Success(None)


def _locked(spec: RecordSpec, record_id: UUID) -> Versioned | None:
    row = spec.all_rows().select_for_update().filter(pk=record_id).first()
    return row if isinstance(row, Versioned) else None


def _is_admin(actor: User) -> bool:
    return Role(actor.role) == Role.ADMIN


def dependents_of(kind: str, record_id: UUID) -> list[str]:
    counts = admin_record_reads.dependent_counts(kind, record_id)
    return [count_text(item.count, item.reason) for item in delete_refusal(kind, counts)]


def _clean_field(key: str, value: object) -> Result[object]:
    match key:
        case "name":
            return check_name(str(value))
        case "code":
            return check_code(str(value))
        case "colour":
            return check_colour(str(value))
        case "time_zone":
            return check_time_zone(str(value), available_timezones())
        case _:
            return Success(value.strip() if isinstance(value, str) else value)


def _cleaned(
    spec: RecordSpec, values: dict[str, object], *, creating: bool
) -> tuple[dict[str, object], list[FieldMessage]]:
    """The values of the record's own fields, normalised; unknown keys never get through."""
    wanted = {key: values[key] for key in spec.fields if key in values}
    if creating:
        for key in ("name", "code"):
            wanted.setdefault(key, "")
        if spec.parent_field:
            wanted.setdefault(spec.parent_field, None)
    cleaned: dict[str, object] = {}
    messages: list[FieldMessage] = []
    for key, value in wanted.items():
        checked = _clean_field(key, value)
        if isinstance(checked, Failure):
            messages += _messages_of(checked)
        else:
            cleaned[key] = checked.value
    return cleaned, messages


def _messages_of(failure: Failure) -> list[FieldMessage]:
    fields = failure.details["fields"]
    if not isinstance(fields, list):
        return []
    return [
        FieldMessage(str(item["field"]), str(item["message"]))
        for item in fields
        if isinstance(item, dict)
    ]


def _parent_and_code_messages(
    spec: RecordSpec, changed: dict[str, object], row: Model | None
) -> list[FieldMessage]:
    messages: list[FieldMessage] = []
    parent_id = changed.get(spec.parent_field) if spec.parent_field else None
    if spec.parent_field and spec.parent_field in changed and spec.parent_model is not None:
        is_there = isinstance(parent_id, UUID) and (
            spec.parent_model._default_manager.select_for_update().filter(pk=parent_id).exists()
        )
        if not is_there:
            messages.append(
                FieldMessage(spec.parent_form_name, f"Choose a {spec.parent_form_name}.")
            )
    code = changed.get("code")
    if isinstance(code, str) and code:
        taken = spec.all_rows().filter(code__iexact=code)
        if row is not None:
            taken = taken.exclude(pk=row.pk)
        if taken.exists():
            messages.append(FieldMessage("code", CODE_TAKEN))
    return messages


def _room_move_messages(changed: dict[str, object], row: Model) -> list[FieldMessage]:
    if not isinstance(row, Room) or "department_id" not in changed:
        return []
    users = ClinicianProfile.objects.filter(
        default_room_id=row.pk,
        department_id=row.department_id,
    ).count()
    if users == 0:
        return []
    verb = "uses" if users == 1 else "use"
    text = f"{count_text(users, 'clinicians')} {verb} this room as their default room."
    return [FieldMessage("department", f"{text} Change theirs first.")]


def _saved(spec: RecordSpec, row: Model) -> Failure | None:
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as error:
        cause = error.__cause__
        if isinstance(cause, psycopg.errors.UniqueViolation) and (
            cause.diag.constraint_name == spec.code_constraint
        ):
            return Failure.invalid_input([FieldMessage("code", CODE_TAKEN)])
        raise
    return None


def _audit(
    spec: RecordSpec,
    verb: str,
    row: Model,
    changed: tuple[str, ...],
    actor: User,
    entity_id: UUID | None = None,
) -> None:
    """`entity_id` is for delete: Django clears the key of a deleted row."""
    parent_id = getattr(row, spec.parent_field) if spec.parent_field and verb != "delete" else None
    metadata = AuditMetadata(
        ids={spec.parent_field: parent_id} if parent_id is not None else {},
        changed_fields=changed_field_names(
            spec.model, [name.removesuffix("_id") for name in changed]
        ),
    )
    event = AuditEvent(
        f"{spec.kind}.{verb}", spec.model.__name__, str(entity_id or row.pk), metadata
    )
    record_audit(event, actor)
