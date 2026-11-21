"""Section 9.3: availability rules and time off are audited writes of the clinician's own rows."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, AvailabilityRule, TimeOff, User
from scheduling.models.builders import STARTS_AT, Clinic, add_clinician, make, make_clinic
from scheduling.use_cases.availability import RuleCommand
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

CONTEXT = RequestContext(correlation_id="corr-rule", now=datetime(2030, 1, 7, 6, 0, tzinfo=UTC))
WEDNESDAY = 3
PLANTED_REASON = "planted-time-off-reason-8812"


def _actor(clinic: Clinic) -> User:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return user


def _command(room_id: object = None, **overrides: object) -> RuleCommand:

    fields = {
        "weekday": WEDNESDAY,
        "start_time": time(10, 0),
        "end_time": time(12, 0),
        "slot_step_minutes": 30,
        "room_id": room_id,
        **overrides,
    }
    return RuleCommand(**fields)  # type: ignore[arg-type]  # noqa: PGH003 - test builds from a dict


def _create(clinic: Clinic, **overrides: object) -> object:
    from scheduling.use_cases.availability import create_rule

    with bind_request_context(CONTEXT):
        return create_rule(_command(**overrides), _actor(clinic))


def _audit(action: str) -> list[AuditLogEntry]:
    return list(AuditLogEntry.objects.filter(action=action))


def returns_creates_rule_and_audits_in_same_transaction() -> None:
    clinic = make_clinic()

    result = _create(clinic)

    assert isinstance(result, Success)
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician, weekday=WEDNESDAY)
    assert (rule.version, rule.valid_from, rule.valid_to) == (1, CONTEXT.now.date(), None)
    entry = _audit("availability.create")[0]
    assert (entry.entity_type, entry.entity_id) == ("AvailabilityRule", str(rule.pk))
    assert entry.metadata["ids"]["clinician_id"] == str(clinic.clinician.pk)


def returns_rolls_back_rule_when_audit_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from scheduling.use_cases import availability

    clinic = make_clinic()

    def broken(*_: object) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr(availability, "record_audit", broken)

    with pytest.raises(RuntimeError):
        _create(clinic)

    assert not AvailabilityRule.objects.filter(weekday=WEDNESDAY).exists()


def returns_invalid_input_when_rule_overlaps_existing_one() -> None:
    clinic = make_clinic()

    result = _create(clinic, weekday=1, start_time=time(16, 59), end_time=time(18, 0))

    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT
    assert AvailabilityRule.objects.filter(clinician=clinic.clinician).count() == 1
    assert _audit("availability.create") == []


def returns_invalid_input_when_room_of_other_department() -> None:
    clinic = make_clinic()
    foreign_room = make("Room", department=make("Department"))

    result = _create(clinic, room_id=foreign_room.pk)

    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT


def returns_invalid_input_when_room_inactive() -> None:
    clinic = make_clinic()
    room = make("Room", department=clinic.department, is_active=False)

    result = _create(clinic, room_id=room.pk)

    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT


def returns_update_raises_version_to_2_and_audits() -> None:
    from scheduling.use_cases.availability import update_rule

    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)

    with bind_request_context(CONTEXT):
        result = update_rule(rule.pk, _command(weekday=1), _actor(clinic))

    assert isinstance(result, Success)
    rule.refresh_from_db()
    assert (rule.version, rule.start_time, rule.slot_step_minutes) == (2, time(10, 0), 30)
    assert len(_audit("availability.update")) == 1


def returns_delete_removes_row_and_audits() -> None:
    from scheduling.use_cases.availability import delete_rule

    clinic = make_clinic()
    rule = AvailabilityRule.objects.get(clinician=clinic.clinician)

    with bind_request_context(CONTEXT):
        result = delete_rule(rule.pk, _actor(clinic))

    assert isinstance(result, Success)
    assert not AvailabilityRule.objects.filter(pk=rule.pk).exists()
    assert _audit("availability.delete")[0].entity_id == str(rule.pk)


def returns_forbidden_when_other_clinicians_rule() -> None:
    from scheduling.use_cases.availability import delete_rule, update_rule

    clinic = make_clinic()
    other = add_clinician(clinic.department)
    foreign = AvailabilityRule.objects.get(clinician=other)

    with bind_request_context(CONTEXT):
        deleted = delete_rule(foreign.pk, _actor(clinic))
        updated = update_rule(foreign.pk, _command(weekday=1), _actor(clinic))

    assert deleted == Failure.forbidden() and updated == Failure.forbidden()
    foreign.refresh_from_db()
    assert foreign.version == 1
    assert AuditLogEntry.objects.count() == 0


def returns_not_found_when_rule_missing() -> None:
    from scheduling.use_cases.availability import delete_rule

    clinic = make_clinic()

    with bind_request_context(CONTEXT):
        assert delete_rule(uuid4(), _actor(clinic)) == Failure.not_found()


def _time_off(
    clinic: Clinic, starts_at: datetime = STARTS_AT, reason: str = PLANTED_REASON
) -> object:
    from scheduling.use_cases.time_off import TimeOffCommand, create_time_off

    command = TimeOffCommand(starts_at, starts_at + timedelta(hours=2), reason)
    with bind_request_context(CONTEXT):
        return create_time_off(command, _actor(clinic))


def returns_creates_time_off_and_audits_without_the_reason() -> None:
    clinic = make_clinic()

    result = _time_off(clinic)

    assert isinstance(result, Success)
    assert TimeOff.objects.get(clinician=clinic.clinician).version == 1
    entry = _audit("time_off.create")[0]
    assert PLANTED_REASON not in str(entry.metadata)


def returns_stores_time_off_reason_without_surrounding_spaces() -> None:
    clinic = make_clinic()

    _time_off(clinic, reason="  Conference  ")

    assert TimeOff.objects.get(clinician=clinic.clinician).reason == "Conference"


def returns_invalid_input_when_identical_time_off_recorded_twice() -> None:
    clinic = make_clinic()
    _time_off(clinic)

    result = _time_off(clinic)

    assert isinstance(result, Failure) and result.code == FailureCode.INVALID_INPUT
    assert TimeOff.objects.filter(clinician=clinic.clinician).count() == 1


def returns_leaves_appointment_inside_time_off_booked() -> None:
    clinic = make_clinic()
    visit = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )

    _time_off(clinic)

    assert Appointment.objects.get(pk=visit.pk).status == "BOOKED"


def returns_forbidden_when_deleting_other_clinicians_time_off() -> None:
    from scheduling.use_cases.time_off import delete_time_off

    clinic = make_clinic()
    foreign = make("TimeOff", clinician=add_clinician(clinic.department))

    with bind_request_context(CONTEXT):
        result = delete_time_off(foreign.pk, _actor(clinic))

    assert result == Failure.forbidden()
    assert TimeOff.objects.filter(pk=foreign.pk).exists()


def returns_deletes_own_time_off_and_audits() -> None:
    from scheduling.use_cases.time_off import delete_time_off

    clinic = make_clinic()
    own = make("TimeOff", clinician=clinic.clinician)

    with bind_request_context(CONTEXT):
        result = delete_time_off(own.pk, _actor(clinic))

    assert isinstance(result, Success)
    assert not TimeOff.objects.filter(pk=own.pk).exists()
    assert len(_audit("time_off.delete")) == 1
