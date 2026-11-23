"""The patient's own profile and password, each write audited."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.contrib.auth.hashers import check_password
from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.profile_rules import (
    birth_date_failure,
    new_password_failures,
    phone_failure,
)
from scheduling.models import Session, User
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.sign_in import is_locked_out, record_wrong_password

CURRENT_MISMATCH_MESSAGE = "The current password is not right."
CURRENT_MISSING_MESSAGE = "Enter your current password."
NEW_MISSING_MESSAGE = "Enter a new password."


@dataclass(frozen=True)
class ProfileCommand:
    phone: str
    date_of_birth: date | None


def update_profile(
    command: ProfileCommand, actor: User, expected_version: int | None = None
) -> Result[None]:
    today = current_request_context().now.date()
    failures = [phone_failure(command.phone)]
    if command.date_of_birth is not None:
        failures.append(birth_date_failure(command.date_of_birth, today))
    problems = [item for item in failures if item is not None]
    if problems:
        return Failure.invalid_input(problems)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=actor.pk)
        if expected_version not in (None, user.version):
            return stale_version()
        changed = []
        if user.phone != command.phone:
            user.phone = command.phone
            changed.append("phone")
        if user.date_of_birth != command.date_of_birth:
            user.date_of_birth = command.date_of_birth
            changed.append("date_of_birth")
        if changed:
            user.save()
            metadata = AuditMetadata(changed_fields=changed_field_names(User, changed))
            record_audit(AuditEvent("profile.update", "User", str(user.pk), metadata), actor)
    return Success(None)


def change_password(
    current: str, new: str, actor: User, keep_session_id: UUID | None
) -> Result[None]:
    if not actor.has_usable_password():
        return Failure.forbidden()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=actor.pk)
        if is_locked_out(user.email):
            return _current_mismatch()
        problems = _new_password_problems(current, new)
        if not current:
            problems.insert(0, FieldMessage("current_password", CURRENT_MISSING_MESSAGE))
        elif not check_password(current, user.password):
            record_wrong_password(user)
            problems.insert(0, FieldMessage("current_password", CURRENT_MISMATCH_MESSAGE))
        if problems:
            return Failure.invalid_input(problems)
        user.set_password(new)
        user.save()
        ended = Session.objects.filter(user=user)
        if keep_session_id is not None:
            ended = ended.exclude(pk=keep_session_id)
        ended_count, _ = ended.delete()
        metadata = AuditMetadata(
            counts={"session_count": ended_count},
            changed_fields=changed_field_names(User, ["password"]),
        )
        record_audit(AuditEvent("auth.password_change", "User", str(user.pk), metadata), actor)
    return Success(None)


def _new_password_problems(current: str, new: str) -> list[FieldMessage]:
    if not new:
        return [FieldMessage("new_password", NEW_MISSING_MESSAGE)]
    return new_password_failures(current, new)


def _current_mismatch() -> Result[None]:
    return Failure.invalid_input([FieldMessage("current_password", CURRENT_MISMATCH_MESSAGE)])
