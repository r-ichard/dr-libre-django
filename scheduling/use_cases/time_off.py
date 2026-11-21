"""Section 9.3: a clinician's time off. Recording it never touches booked appointments; the page
lists them beforehand. The audit entry holds ids only: the reason is free text."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.time_off_rules import time_off_failures
from scheduling.models import TimeOff, User
from scheduling.use_cases.audit import AuditEvent, changed_field_names, record_audit
from scheduling.use_cases.availability import locked_profile
from scheduling.use_cases.record_access import guard_record

TIME_OFF_FIELDS = ("starts_at", "ends_at", "reason")
REPEATED_PERIOD = FieldMessage("starts_at", "This period is already recorded.")


@dataclass(frozen=True)
class TimeOffCommand:
    starts_at: datetime
    ends_at: datetime
    reason: str


def create_time_off(command: TimeOffCommand, actor: User) -> Result[TimeOff]:
    with transaction.atomic():
        profile = locked_profile(actor)
        if isinstance(profile, Failure):
            return profile
        existing = list(
            TimeOff.objects.filter(clinician=profile.value).values_list("starts_at", "ends_at")
        )
        failures = time_off_failures(command.starts_at, command.ends_at, command.reason, existing)
        if failures:
            return Failure.invalid_input(failures)
        row = TimeOff(
            clinician=profile.value,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            reason=command.reason.strip(),
            created_by=actor,
        )
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError:
            return Failure.invalid_input([REPEATED_PERIOD])
        _audit("time_off.create", row, TIME_OFF_FIELDS, actor)
        return Success(row)


def delete_time_off(time_off_id: UUID, actor: User) -> Result[UUID]:
    with transaction.atomic():
        profile = locked_profile(actor)
        if isinstance(profile, Failure):
            return profile
        row = TimeOff.objects.select_for_update().filter(pk=time_off_id).first()
        found = guard_record(row, lambda found: found.clinician_id == profile.value.pk)
        if isinstance(found, Failure):
            return found
        _audit("time_off.delete", found.value, (), actor)
        found.value.delete()
        return Success(time_off_id)


def _audit(action: str, row: TimeOff, changed: tuple[str, ...], actor: User) -> None:
    metadata = AuditMetadata(
        ids={"clinician_id": row.clinician_id},
        changed_fields=changed_field_names(TimeOff, changed),
    )
    record_audit(AuditEvent(action, "TimeOff", str(row.pk), metadata), actor)
