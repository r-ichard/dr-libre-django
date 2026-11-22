"""Section 10: create, update, deactivate and delete of a user. One transaction per change: lock
(actor and target in primary key order), version, rules, save, audit. The password is hashed
here and appears in no value, audit entry or log line."""

from uuid import UUID

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from scheduling.domain import user_rules
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.delete_dependents import delete_refusal
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.user_rules import RoleFacts
from scheduling.domain.vocabulary import Role
from scheduling.models import Appointment, Notification, Session, SignInLink, User, WaitlistEntry
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.admin_record_specs import count_text
from scheduling.use_cases.admin_records import RecordEdit
from scheduling.use_cases.admin_user_support import (
    EMAIL_TAKEN,
    USE_DEACTIVATE_STEP,
    Locked,
    cleaned_values,
    email_is_taken,
    end_access,
    is_email_conflict,
    lock_users,
)
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit


def create_user(values: dict[str, object], actor: User) -> Result[UUID]:
    with transaction.atomic():
        if lock_users(actor.pk, None).admin is None:
            return Failure.forbidden()
        cleaned, messages = cleaned_values(values, creating=True)
        email = cleaned.get("email")
        if isinstance(email, str) and email_is_taken(email, None):
            messages.append(FieldMessage("email", EMAIL_TAKEN))
        if messages:
            return Failure.invalid_input(messages)
        password = str(cleaned.pop("password"))
        user = User(**cleaned, created_by=actor, password=make_password(password))
        refused = _saved(user)
        if refused is not None:
            return refused
        _audit("create", user.pk, ["full_name", "email", "role", "password"], actor)
        return Success(user.pk)


def update_user(edit: RecordEdit, actor: User, expected_version: int | None = None) -> Result[UUID]:
    with transaction.atomic():
        locked = lock_users(actor.pk, edit.record_id)
        if locked.admin is None:
            return Failure.forbidden()
        if locked.target is None:
            return Failure.not_found()
        target = locked.target
        if expected_version not in (None, target.version):
            return stale_version()
        if target.version != edit.version:
            return Failure.conflict(["user"])
        cleaned, messages = cleaned_values(edit.values, creating=False)
        cleaned.pop("password", None)
        changed = {key: value for key, value in cleaned.items() if getattr(target, key) != value}
        messages += _update_messages(changed, locked, actor)
        if messages:
            return Failure.invalid_input(messages)
        if not changed:
            return Success(target.pk)
        return _apply_update(target, changed, actor)


def _apply_update(target: User, changed: dict[str, object], actor: User) -> Result[UUID]:
    names = list(changed)
    counts: dict[str, int] = {}
    if "email" in changed:
        target.email_verified_at = None
        names.append("email_verified_at")
        sessions, links = end_access(target)
        counts = {"session_count": sessions, "link_count": links}
    for key, value in changed.items():
        setattr(target, key, value)
    refused = _saved(target)
    if refused is not None:
        return refused
    only_active = list(changed) == ["is_active"]
    _audit("activate" if only_active else "update", target.pk, names, actor, counts)
    return Success(target.pk)


def _update_messages(changed: dict[str, object], locked: Locked, actor: User) -> list[FieldMessage]:
    target = locked.target
    assert target is not None  # noqa: S101 - the caller returned not_found before
    messages: list[FieldMessage] = []
    if changed.get("is_active") is False:
        messages.append(FieldMessage("is_active", USE_DEACTIVATE_STEP))
    email = changed.get("email")
    if isinstance(email, str):
        if email_is_taken(email, target.pk):
            messages.append(FieldMessage("email", EMAIL_TAKEN))
        reason = user_rules.email_change_refusal(is_passwordless=not target.has_usable_password())
        messages += [FieldMessage("email", reason)] if reason else []
    role = changed.get("role")
    if isinstance(role, str):
        messages += _role_messages(Role(role), locked, actor)
    return messages


def _role_messages(new: Role, locked: Locked, actor: User) -> list[FieldMessage]:
    target = locked.target
    assert target is not None  # noqa: S101 - the caller returned not_found before
    current = Role(target.role)
    facts = RoleFacts(
        current,
        new,
        hasattr(target, "clinicianprofile"),
        Appointment.objects.filter(patient=target).count(),
        WaitlistEntry.objects.filter(patient=target).count(),
        not target.has_usable_password(),
    )
    reasons = user_rules.own_account_refusals(
        is_own_account=target.pk == actor.pk, deactivates=False, changes_role=True
    )
    reasons += user_rules.role_change_refusals(facts)
    last = user_rules.last_admin_refusal(
        locked.active_admins, _is_active_admin(target), new == Role.ADMIN
    )
    return [FieldMessage("role", text) for text in [*reasons, *([last] if last else [])]]


def _is_active_admin(user: User) -> bool:
    return user.is_active and Role(user.role) == Role.ADMIN


def deactivate_user(user_id: UUID, version: int, actor: User) -> Result[UUID]:
    with transaction.atomic():
        locked = lock_users(actor.pk, user_id)
        if locked.admin is None:
            return Failure.forbidden()
        target = locked.target
        if target is None:
            return Failure.not_found()
        if target.version != version:
            return Failure.conflict(["user"])
        reasons = user_rules.own_account_refusals(
            is_own_account=target.pk == actor.pk, deactivates=True, changes_role=False
        )
        last = user_rules.last_admin_refusal(locked.active_admins, _is_active_admin(target), False)
        reasons += [last] if last else []
        if reasons:
            return Failure.rule_violation(reasons)
        if not target.is_active:
            return Success(target.pk)
        target.is_active = False
        target.save()
        sessions, links = end_access(target)
        counts = {"session_count": sessions, "link_count": links}
        _audit("deactivate", target.pk, ["is_active"], actor, counts)
        return Success(target.pk)


def delete_user(user_id: UUID, actor: User) -> Result[None]:
    with transaction.atomic():
        locked = lock_users(actor.pk, user_id)
        if locked.admin is None:
            return Failure.forbidden()
        if locked.target is None:
            return Failure.not_found()
        blocked = user_dependents(user_id, actor.pk)
        if blocked:
            return Failure.has_dependents(blocked)
        try:
            with transaction.atomic():
                Session.objects.filter(user=locked.target).delete()
                SignInLink.objects.filter(patient=locked.target).delete()
                Notification.objects.filter(recipient=locked.target).delete()
                locked.target.delete()
        except (ProtectedError, IntegrityError):
            return Failure.has_dependents(user_dependents(user_id, actor.pk) or ["records it made"])
        _audit("delete", user_id, [], actor)
        return Success(None)


def user_dependents(user_id: UUID, actor_id: UUID) -> list[str]:
    """What stops a delete, in words. The own account is a count of 1 so the table rule is one."""
    counts = admin_record_reads.dependent_counts("user", user_id)
    counts["own_account"] = int(user_id == actor_id)
    return [_reason_text(item.reason, item.count) for item in delete_refusal("user", counts)]


def _reason_text(reason: str, count: int) -> str:
    if reason == "own_account":
        return "your own account"
    return count_text(count, reason)


def _saved(user: User) -> Failure | None:
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as error:
        if is_email_conflict(error):
            return Failure.invalid_input([FieldMessage("email", EMAIL_TAKEN)])
        raise
    return None


def _audit(
    verb: str, user_id: UUID, names: list[str], actor: User, counts: dict[str, int] | None = None
) -> None:
    metadata = AuditMetadata(counts=counts or {}, changed_fields=changed_field_names(User, names))
    record_audit(AuditEvent(f"user.{verb}", "User", str(user_id), metadata), actor)
