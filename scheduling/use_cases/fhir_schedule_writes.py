"""Task 23, spec 15.1, 15.2: Schedule writes. Each goes through the use case the clinician's
screen calls (overlap rule, room, audit, version) after the body is read as the fields of one
rule. Only the clinician the schedule is for may write it."""

from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.availability_rules import new_rule_validity
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.fhir_common import Resource
from scheduling.domain.fhir_schedule import (
    ScheduleFields,
    horizon,
    schedule_fields,
    server_owned_problem,
)
from scheduling.models import AvailabilityRule, User
from scheduling.use_cases import fhir_loading as loading
from scheduling.use_cases.availability import (
    OVERLAP_MESSAGE,
    RuleCommand,
    create_rule,
    delete_rule,
    update_rule,
)
from scheduling.use_cases.clinician_agenda import clinician_profile_of
from scheduling.use_cases.fhir_caller import Caller
from scheduling.use_cases.request_context import current_request_context

ELEMENT_MESSAGE = "This element is not valid."


def create_schedule(body: dict[str, object], caller: Caller) -> Result[Resource]:
    fields = _own_fields(body, caller)
    if isinstance(fields, Failure):
        return fields
    user = _user(caller)
    profile = clinician_profile_of(user)
    if profile is None:
        return Failure.forbidden()
    zone = ZoneInfo(profile.department.hospital.time_zone)
    today = current_request_context().now.astimezone(zone).date()
    problem = server_owned_problem(body, horizon(*new_rule_validity(today)))
    if problem is not None:
        return _invalid(problem)
    created = create_rule(_command(fields), user)
    return _built(created)


def update_schedule(
    identifier: UUID, body: dict[str, object], caller: Caller, expected_version: int | None
) -> Result[Resource]:
    fields = _own_fields(body, caller)
    if isinstance(fields, Failure):
        return fields
    stored = AvailabilityRule.objects.filter(pk=identifier).first()
    if stored is None:
        return Failure.not_found()
    problem = server_owned_problem(body, horizon(stored.valid_from, stored.valid_to))
    if problem is not None:
        return _invalid(problem)
    updated = update_rule(identifier, _command(fields), _user(caller), expected_version)
    return _built(updated)


def delete_schedule(identifier: UUID, caller: Caller, expected_version: int | None) -> Result[None]:
    deleted = delete_rule(identifier, _user(caller), expected_version)
    return deleted if isinstance(deleted, Failure) else Success(None)


def _user(caller: Caller) -> User:
    if caller.user is None:
        raise ValueError("a write reaches a use case with a token's user")
    return caller.user


def _own_fields(body: dict[str, object], caller: Caller) -> ScheduleFields | Failure:
    fields = schedule_fields(body)
    if isinstance(fields, str):
        return _invalid(fields)
    if fields.practitioner_id != _user(caller).pk:
        return Failure.forbidden()
    return fields


def _command(fields: ScheduleFields) -> RuleCommand:
    return RuleCommand(
        fields.weekday, fields.start_time, fields.end_time, fields.slot_step_minutes, fields.room_id
    )


def _invalid(element: str) -> Failure:
    return Failure.invalid_input([FieldMessage(element, ELEMENT_MESSAGE)])


def _built(written: Result[AvailabilityRule]) -> Result[Resource]:
    if isinstance(written, Failure):
        return _overlap_as_rule_violation(written)
    return Success(loading.schedules([written.value.pk])[0])


def _overlap_as_rule_violation(failure: Failure) -> Failure:
    """An overlap is a rule of the schedule being broken (422), not a malformed element."""
    fields = failure.details.get("fields", [])
    names = (
        [item.get("message") for item in fields if isinstance(item, dict)]
        if isinstance(fields, list)
        else []
    )
    if OVERLAP_MESSAGE.message in names:
        return Failure.rule_violation([OVERLAP_MESSAGE.message])
    return failure
