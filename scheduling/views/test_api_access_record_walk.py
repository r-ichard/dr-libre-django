"""The walk over the routes that name a record. Each caller sends each such request for its own
record and for another user's, and gets the row's answer, or the rule's for the other's. A refused
request leaves the record and the audit log unchanged."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from django.db.models import Model

from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    ClinicianProfile,
    Hospital,
    Specialty,
    WaitlistEntry,
)
from scheduling.views import clock
from scheduling.views.test_api_access_record_requests import RECORD_SENDERS
from scheduling.views.test_api_access_record_world import (
    RecordWorld,
    _appointment_pair,
    _build_record_world,
    _waitlist_pair,
)
from scheduling.views.test_api_access_rows import (
    API_ACCESS_ROWS,
    KNOWN_DIFFERENCES,
    AccessRow,
    Caller,
    RecordUse,
)
from scheduling.views.test_api_access_walk import HOLD_ROUTE_PREFIX
from scheduling.views.test_api_access_world import World, _build_world

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SUCCESS = 200
REFUSED = 400
FORBIDDEN = 403
NOT_FOUND = 404
APPOINTMENT_PREFIX = "api/v1/appointments/"
CATALOG_PREFIXES = ("api/v1/hospitals/", "api/v1/providers/", "api/v1/specialties/")
RECORD_ROWS = tuple(
    row
    for row in API_ACCESS_ROWS
    if "<" in row.route and not row.route.startswith(HOLD_ROUTE_PREFIX)
)


@dataclass(frozen=True)
class RecordPair:
    """The caller's own record and another user's, and the model both belong to."""

    model: type[Model]
    own: UUID
    other: UUID


def _is_catalog(row: AccessRow) -> bool:
    return row.route.startswith(CATALOG_PREFIXES)


def _expected(row: AccessRow, caller: Caller, use: RecordUse) -> int:
    """The row's answer. For another user's record a signed-in patient or clinician gets 403 where
    the row allows the route; a public catalog record is inactive, so it is 404 for everyone."""
    cell = row.answer_for(caller)
    if _is_catalog(row):
        return NOT_FOUND if use is RecordUse.OTHER else cell
    if use is RecordUse.OWN or caller in (Caller.VISITOR, Caller.ADMIN):
        return cell
    return FORBIDDEN if cell == SUCCESS else cell


def _wanted(row: AccessRow, caller: Caller, use: RecordUse) -> int:
    for difference in KNOWN_DIFFERENCES:
        same_request = (difference.caller, difference.method, difference.route) == (
            caller,
            row.method,
            row.route,
        )
        if difference.record is use and same_request:
            return difference.product_answer
    return _expected(row, caller, use)


def _catalog_pair(row: AccessRow, world: World, record_world: RecordWorld) -> RecordPair:
    if row.route.startswith("api/v1/hospitals/"):
        hospital = world.appointment_type.department.hospital
        return RecordPair(Hospital, hospital.pk, record_world.inactive_hospital.pk)
    if row.route.startswith("api/v1/providers/"):
        return RecordPair(ClinicianProfile, world.clinician.pk, record_world.inactive_provider.pk)
    specialty = world.clinician.specialty
    return RecordPair(Specialty, specialty.pk, record_world.inactive_specialty.pk)


def _pair_for(row: AccessRow, world: World, record_world: RecordWorld) -> RecordPair:
    """Fresh records for each request, except the catalog, which no walked request changes."""
    if _is_catalog(row):
        return _catalog_pair(row, world, record_world)
    if row.route.startswith(APPOINTMENT_PREFIX):
        return _appointment_pair_for(row, world, record_world)
    return _waitlist_pair_for(row, world, record_world)


def _appointment_pair_for(row: AccessRow, world: World, record_world: RecordWorld) -> RecordPair:
    completing = row.route.endswith("/complete")
    status = AppointmentStatus.CHECKED_IN if completing else AppointmentStatus.BOOKED
    own, other = _appointment_pair(record_world, world, status)
    return RecordPair(Appointment, own.pk, other.pk)


def _waitlist_pair_for(row: AccessRow, world: World, record_world: RecordWorld) -> RecordPair:
    accepting = row.route.endswith("/accept")
    status = WaitlistStatus.OFFERED if accepting else WaitlistStatus.WAITING
    own, other = _waitlist_pair(record_world, world, status)
    return RecordPair(WaitlistEntry, own.pk, other.pk)


def _snapshot(model: type[Model], pk: UUID) -> dict[str, object] | None:
    row: dict[str, object] | None = model._default_manager.filter(pk=pk).values().first()
    return row


def _request_problem(
    row: AccessRow, caller: Caller, use: RecordUse, world: World, record_world: RecordWorld
) -> str | None:
    pair = _pair_for(row, world, record_world)
    record_id = pair.own if use is RecordUse.OWN else pair.other
    wanted = _wanted(row, caller, use)
    before = _snapshot(pair.model, record_id)
    audits_before = AuditLogEntry.objects.count()
    sender = RECORD_SENDERS[(row.method, row.route)]
    got = sender(world, caller, record_id).status_code
    label = f"{row.method} {row.route} as {caller} on {use}"
    if got != wanted:
        return f"{label}: expected {wanted}, got {got}"
    changed = _snapshot(pair.model, record_id) != before
    if wanted >= REFUSED and (changed or AuditLogEntry.objects.count() != audits_before):
        return f"{label}: refused, yet the record or the audit log changed"
    if use is RecordUse.OWN and row.method == "POST" and wanted < REFUSED and not changed:
        return f"{label}: accepted, yet the record did not change"
    return None


def _walk_problems(world: World, record_world: RecordWorld) -> list[str]:
    problems: list[str] = []
    for row in RECORD_ROWS:
        for caller in Caller:
            for use in RecordUse:
                problem = _request_problem(row, caller, use, world, record_world)
                if problem is not None:
                    problems.append(problem)
    return problems


def _difference_problems() -> list[str]:
    problems: list[str] = []
    for difference in KNOWN_DIFFERENCES:
        if difference.record is None:
            continue
        label = (
            f"{difference.method} {difference.route} as {difference.caller} on {difference.record}"
        )
        row = next(
            (
                candidate
                for candidate in RECORD_ROWS
                if (candidate.method, candidate.route) == (difference.method, difference.route)
            ),
            None,
        )
        if row is None:
            problems.append(f"{label}: not a walked record row")
            continue
        spec = _expected(row, difference.caller, difference.record)
        if difference.row_answer != spec:
            problems.append(f"{label}: row_answer {difference.row_answer} is not the spec's {spec}")
        if difference.product_answer == spec:
            problems.append(f"{label}: product answer {spec} is the spec's, so the entry is stale")
    return problems


def returns_the_expected_answer_and_unchanged_record_for_each_caller_when_walk_names_each_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    world = _build_world()
    record_world = _build_record_world(world)

    problems = _difference_problems() + _walk_problems(world, record_world)

    assert problems == []
