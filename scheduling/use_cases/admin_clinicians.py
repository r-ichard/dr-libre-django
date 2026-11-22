"""Section 10: attach, edit and delete a clinician profile. One transaction per change: lock the
admin and the rows, version, rules, save, audit. Public search reads live rows, so it follows
at once."""

from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from scheduling.domain import clinician_rules, record_fields
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import Role
from scheduling.models import (
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Room,
    Specialty,
    User,
)
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.admin_record_specs import count_text
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_user_support import lock_users
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.request_context import current_request_context

FIELDS = ("user_id", "department_id", "specialty_id", "title", "bio", "default_room_id")
BIO_LENGTH = 2000
NOT_A_CLINICIAN = "Choose an active clinician without a profile."
CHOOSE_DEPARTMENT = "Choose a department."
CHOOSE_SPECIALTY = "Choose an active specialty."
CHOOSE_ROOM = "Choose an active room of this department."


def attach_profile(values: dict[str, object], actor: User) -> Result[UUID]:
    with transaction.atomic():
        user_id = values.get("user_id")
        locked = lock_users(actor.pk, user_id if isinstance(user_id, UUID) else None)
        if locked.admin is None:
            return Failure.forbidden()
        cleaned, messages = _cleaned(values, creating=True)
        messages += _user_messages(locked.target)
        messages += _reference_messages(cleaned, None)
        if messages:
            return Failure.invalid_input(messages)
        profile = ClinicianProfile(**cleaned, created_by=actor)
        try:
            with transaction.atomic():
                profile.save()
        except IntegrityError:
            return Failure.invalid_input([FieldMessage("user", NOT_A_CLINICIAN)])
        _audit("create", profile, [*cleaned], actor)
        return Success(profile.pk)


def update_profile(edit: RecordEdit, actor: User) -> Result[UUID]:
    with transaction.atomic():
        if lock_users(actor.pk, None).admin is None:
            return Failure.forbidden()
        profile = ClinicianProfile.objects.select_for_update().filter(pk=edit.record_id).first()
        if profile is None:
            return Failure.not_found()
        if profile.version != edit.version:
            return Failure.conflict(["clinician"])
        cleaned, messages = _cleaned(edit.values, creating=False)
        cleaned.pop("user_id", None)
        changed = {key: value for key, value in cleaned.items() if getattr(profile, key) != value}
        messages += _reference_messages(changed, profile)
        messages += _move_messages(profile, changed)
        if messages:
            return Failure.invalid_input(messages)
        if not changed:
            return Success(profile.pk)
        for key, value in changed.items():
            setattr(profile, key, value)
        profile.save()
        _audit("update", profile, [*changed], actor)
        return Success(profile.pk)


def delete_profile(record_id: UUID, actor: User) -> Result[None]:
    with transaction.atomic():
        if lock_users(actor.pk, None).admin is None:
            return Failure.forbidden()
        profile = ClinicianProfile.objects.select_for_update().filter(pk=record_id).first()
        if profile is None:
            return Failure.not_found()
        blocked = profile_dependents(record_id)
        if blocked:
            return Failure.has_dependents(blocked)
        try:
            with transaction.atomic():
                profile.delete()
        except ProtectedError as error:
            return Failure.has_dependents(_protected_words(error))
        _audit("delete", profile, [], actor, record_id)
        return Success(None)


def profile_dependents(record_id: UUID) -> list[str]:
    counts = admin_record_reads.dependent_counts("clinician", record_id)
    return [count_text(count, reason) for reason, count in counts.items() if count]


def _protected_words(error: ProtectedError) -> list[str]:
    names: dict[str, int] = {}
    for row in error.protected_objects:
        name = str(row._meta.verbose_name_plural)
        names[name] = names.get(name, 0) + 1
    return [f"{count} {name}" for name, count in names.items()]


def _cleaned(
    values: dict[str, object], *, creating: bool
) -> tuple[dict[str, object], list[FieldMessage]]:
    cleaned: dict[str, object] = {key: values[key] for key in FIELDS if key in values}
    messages: list[FieldMessage] = []
    if creating:
        for key in ("department_id", "specialty_id", "user_id"):
            cleaned.setdefault(key, None)
    if "title" in cleaned:
        checked_title = clinician_rules.check_title(str(cleaned["title"]))
        messages += _failure_messages(checked_title)
        cleaned["title"] = getattr(checked_title, "value", "")
    if "bio" in cleaned:
        checked_bio = record_fields.check_text("bio", str(cleaned["bio"]), BIO_LENGTH, None)
        messages += _failure_messages(checked_bio)
        cleaned["bio"] = getattr(checked_bio, "value", "")
    weight = values.get("round_robin_weight", 1 if creating else None)
    if weight is not None:
        weight_result = clinician_rules.check_weight(str(weight))
        messages += _failure_messages(weight_result)
        cleaned["round_robin_weight"] = getattr(weight_result, "value", 1)
    return cleaned, messages


def _failure_messages(result: Result[object]) -> list[FieldMessage]:
    if not isinstance(result, Failure):
        return []
    fields = result.details["fields"]
    items = fields if isinstance(fields, list) else []
    return [FieldMessage(str(i["field"]), str(i["message"])) for i in items if isinstance(i, dict)]


def _user_messages(user: User | None) -> list[FieldMessage]:
    usable = (
        user is not None
        and user.is_active
        and Role(user.role) == Role.CLINICIAN
        and not ClinicianProfile.objects.filter(user=user).exists()
    )
    return [] if usable else [FieldMessage("user", NOT_A_CLINICIAN)]


def _reference_messages(
    changed: dict[str, object], profile: ClinicianProfile | None
) -> list[FieldMessage]:
    messages: list[FieldMessage] = []
    department_id = changed.get("department_id", profile.department_id if profile else None)
    if "department_id" in changed and not _department_exists(changed["department_id"]):
        messages.append(FieldMessage("department", CHOOSE_DEPARTMENT))
    if "specialty_id" in changed and not _specialty_is_active(changed["specialty_id"]):
        messages.append(FieldMessage("specialty", CHOOSE_SPECIALTY))
    room_id = changed.get("default_room_id")
    if room_id is not None and not _room_fits(room_id, department_id):
        messages.append(FieldMessage("default_room", CHOOSE_ROOM))
    return messages


def _department_exists(key: object) -> bool:
    return isinstance(key, UUID) and Department.objects.select_for_update().filter(pk=key).exists()


def _specialty_is_active(key: object) -> bool:
    if not isinstance(key, UUID):
        return False
    return Specialty.objects.select_for_update().filter(pk=key, is_active=True).exists()


def _room_fits(room_id: object, department_id: object) -> bool:
    if not (isinstance(room_id, UUID) and isinstance(department_id, UUID)):
        return False
    rooms = Room.objects.select_for_update().filter(
        pk=room_id, is_active=True, department_id=department_id
    )
    return rooms.exists()


def _move_messages(profile: ClinicianProfile, changed: dict[str, object]) -> list[FieldMessage]:
    moves = "department_id" in changed
    if not moves:
        return []
    keeps_room = changed.get("default_room_id", profile.default_room_id) is not None
    counts = {
        "upcoming_appointments": upcoming_appointments(profile.pk),
        "availability_rules": AvailabilityRule.objects.filter(clinician=profile).count(),
        "default_room": int(keeps_room),
    }
    reasons = clinician_rules.department_move_refusals(moves=moves, counts=counts)
    return [FieldMessage("department", text) for text in reasons]


def upcoming_appointments(profile_id: UUID) -> int:
    return admin_record_reads.upcoming_for_clinician(profile_id, current_request_context().now)


def _audit(
    verb: str,
    profile: ClinicianProfile,
    names: list[str],
    actor: User,
    entity_id: UUID | None = None,
) -> None:
    ids = {} if verb == "delete" else {"department_id": profile.department_id}
    metadata = AuditMetadata(
        ids=ids,
        changed_fields=changed_field_names(
            ClinicianProfile, [name.removesuffix("_id") for name in names]
        ),
    )
    event = AuditEvent(
        f"clinician.{verb}", "ClinicianProfile", str(entity_id or profile.pk), metadata
    )
    record_audit(event, actor)
