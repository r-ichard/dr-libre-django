"""Section 9.3: availability rules. Each write is one transaction: domain check, version bump,
audit entry. The profile row is locked first so two requests cannot both pass the overlap
check; the room is checked under a row lock (two tables)."""

from dataclasses import dataclass
from datetime import time
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.availability_rules import (
    RoomChoice,
    RuleTimes,
    new_rule_validity,
    rule_failures,
)
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_write_failures import stale_version
from scheduling.domain.vocabulary import Role
from scheduling.models import AvailabilityRule, ClinicianProfile, Room, User
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.clinician_agenda import clinician_profile_of
from scheduling.use_cases.record_access import guard_record
from scheduling.use_cases.request_context import current_request_context

RULE_FIELDS = ("weekday", "start_time", "end_time", "slot_step_minutes", "room")
OVERLAP_MESSAGE = FieldMessage("start_time", "Another rule of that day covers these times.")


@dataclass(frozen=True)
class RuleCommand:
    weekday: int
    start_time: time
    end_time: time
    slot_step_minutes: int
    room_id: UUID | None


def create_rule(command: RuleCommand, actor: User) -> Result[AvailabilityRule]:
    with transaction.atomic():
        locked = locked_profile(actor)
        if isinstance(locked, Failure):
            return locked
        profile = locked.value
        invalid = _invalid(command, profile, exclude_rule_id=None)
        if invalid is not None:
            return invalid
        today = current_request_context().now.astimezone(_zone_of(profile)).date()
        valid_from, valid_to = new_rule_validity(today)
        rule = AvailabilityRule(clinician=profile, valid_from=valid_from, valid_to=valid_to)
        rule.created_by = actor
        return _save_and_audit(rule, command, "availability.create", RULE_FIELDS, actor)


def update_rule(
    rule_id: UUID, command: RuleCommand, actor: User, expected_version: int | None = None
) -> Result[AvailabilityRule]:
    with transaction.atomic():
        locked = locked_profile(actor)
        if isinstance(locked, Failure):
            return locked
        found = _own_rule(rule_id, locked.value, expected_version)
        if isinstance(found, Failure):
            return found
        invalid = _invalid(command, locked.value, exclude_rule_id=rule_id)
        if invalid is not None:
            return invalid
        changed = _changed_names(found.value, command)
        return _save_and_audit(found.value, command, "availability.update", changed, actor)


def delete_rule(rule_id: UUID, actor: User, expected_version: int | None = None) -> Result[UUID]:
    with transaction.atomic():
        locked = locked_profile(actor)
        if isinstance(locked, Failure):
            return locked
        found = _own_rule(rule_id, locked.value, expected_version)
        if isinstance(found, Failure):
            return found
        rule = found.value
        _audit("availability.delete", rule, (), actor)
        rule.delete()
        return Success(rule_id)


def locked_profile(actor: User) -> Result[ClinicianProfile]:
    profile = clinician_profile_of(actor)
    if profile is None or actor.role != Role.CLINICIAN:
        return Failure.forbidden()
    ClinicianProfile.objects.select_for_update().filter(pk=profile.pk).first()
    return Success(profile)


def _zone_of(profile: ClinicianProfile) -> ZoneInfo:
    return ZoneInfo(profile.department.hospital.time_zone)


def _own_rule(
    rule_id: UUID, profile: ClinicianProfile, expected_version: int | None
) -> Result[AvailabilityRule]:
    rule = AvailabilityRule.objects.select_for_update().filter(pk=rule_id).first()
    guarded = guard_record(rule, lambda found: found.clinician_id == profile.pk)
    if isinstance(guarded, Success) and expected_version not in (None, guarded.value.version):
        return stale_version()
    return guarded


def _invalid(
    command: RuleCommand, profile: ClinicianProfile, exclude_rule_id: UUID | None
) -> Failure | None:
    stored = AvailabilityRule.objects.filter(clinician=profile)
    if exclude_rule_id is not None:
        stored = stored.exclude(pk=exclude_rule_id)
    others = [
        RuleTimes(row.weekday, row.start_time, row.end_time, row.slot_step_minutes)
        for row in stored
    ]
    times = RuleTimes(
        command.weekday, command.start_time, command.end_time, command.slot_step_minutes
    )
    failures = rule_failures(times, _room_choice(command.room_id, profile), others)
    return Failure.invalid_input(failures) if failures else None


def _room_choice(room_id: UUID | None, profile: ClinicianProfile) -> RoomChoice | None:
    if room_id is None:
        return None
    room = Room.objects.select_for_update().filter(pk=room_id).first()
    if room is None or room.department_id != profile.department_id:
        return RoomChoice(exists_in_department=False, is_active=False)
    return RoomChoice(exists_in_department=True, is_active=room.is_active)


def _save_and_audit(
    rule: AvailabilityRule,
    command: RuleCommand,
    action: str,
    changed: tuple[str, ...],
    actor: User,
) -> Result[AvailabilityRule]:
    rule.weekday = command.weekday
    rule.start_time = command.start_time
    rule.end_time = command.end_time
    rule.slot_step_minutes = command.slot_step_minutes
    rule.room_id = command.room_id
    try:
        with transaction.atomic():
            rule.save()
    except IntegrityError:
        return Failure.invalid_input([OVERLAP_MESSAGE])
    _audit(action, rule, changed, actor)
    return Success(rule)


def _audit(action: str, rule: AvailabilityRule, changed: tuple[str, ...], actor: User) -> None:
    ids: dict[str, UUID | int] = {"clinician_id": rule.clinician_id}
    if rule.room_id is not None:
        ids["room_id"] = rule.room_id
    metadata = AuditMetadata(ids=ids, changed_fields=changed_field_names(AvailabilityRule, changed))
    record_audit(AuditEvent(action, "AvailabilityRule", str(rule.pk), metadata), actor)


def _changed_names(rule: AvailabilityRule, command: RuleCommand) -> tuple[str, ...]:
    new_values = (
        command.weekday,
        command.start_time,
        command.end_time,
        command.slot_step_minutes,
        command.room_id,
    )
    old_values = (
        rule.weekday,
        rule.start_time,
        rule.end_time,
        rule.slot_step_minutes,
        rule.room_id,
    )
    return tuple(
        name
        for name, old, new in zip(RULE_FIELDS, old_values, new_values, strict=True)
        if old != new
    )
