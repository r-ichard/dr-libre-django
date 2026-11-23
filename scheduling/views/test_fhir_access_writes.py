"""The walk of the /fhir writes in test_fhir_access_write_cases: each caller's answer against its
row, a refused write leaves the record and audit log as they were, an accepted one changes them."""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from django.db.models import Model
from django.test import Client

from scheduling.models import AuditLogEntry
from scheduling.views import clock
from scheduling.views.fhir_test_support import FHIR_JSON, NOW
from scheduling.views.test_fhir_access_requests import _expected_answer
from scheduling.views.test_fhir_access_world import World, _build_world
from scheduling.views.test_fhir_access_write_cases import (
    NOT_WALKED_YET,
    WRITE_CASES,
    WRITE_INTERACTIONS,
    WriteCase,
)
from test_support.fhir_access_rows import FHIR_ACCESS_ROWS, Caller, FhirAccessRow

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

Change = tuple[int, int]
# Records added and removed in a table by one accepted write.
ACCEPTED_ROWS_CHANGE: dict[str, Change] = {"create": (1, 0), "update": (0, 0), "delete": (0, 1)}
NO_CHANGE: Change = (0, 0)


@dataclass(frozen=True)
class Snapshot:
    """The admin's read of a record: the status, the body of a 200, and the ETag."""

    status: int
    body: object
    etag: str


@dataclass(frozen=True)
class Request:
    """What one caller sends for one case: the path, the body (none for a delete), the ETag."""

    path: str
    body: dict[str, object] | None
    etag: str


def _read(world: World, path: str) -> Snapshot:
    response = world.clients[Caller.ADMIN].get(path)
    body = response.json() if response.status_code == 200 else None
    return Snapshot(response.status_code, body, response.headers.get("ETag", ""))


def _audit_ids() -> frozenset[object]:
    return frozenset(AuditLogEntry.objects.values_list("pk", flat=True))


def _table_ids(model: type[Model] | None) -> frozenset[object]:
    if model is None:
        return frozenset()
    return frozenset(model._default_manager.values_list("pk", flat=True))


def _change(before: frozenset[object], after: frozenset[object]) -> Change:
    return len(after - before), len(before - after)


def _send(client: Client, interaction: str, request: Request) -> "_MonkeyPatchedWSGIResponse":
    """A FHIR client's write: a JSON body for POST and PUT, a body-less DELETE with If-Match."""
    if interaction == "create":
        return client.post(request.path, data=json.dumps(request.body), content_type=FHIR_JSON)
    if interaction == "update":
        return client.put(
            request.path,
            data=json.dumps(request.body),
            content_type=FHIR_JSON,
            headers={"If-Match": request.etag},
        )
    return client.delete(request.path, headers={"If-Match": request.etag})


def _row_of(case: WriteCase) -> FhirAccessRow:
    return next(
        row
        for row in FHIR_ACCESS_ROWS
        if (row.resource, row.interaction) == (case.resource, case.interaction)
    )


def _label(case: WriteCase, caller: Caller) -> str:
    kind = f" {case.record}" if case.record else ""
    return f"{case.interaction} {case.resource}{kind} as {caller}"


def _same_value(read: object, sent: object) -> bool:
    # The server returns a list in its own order (the specialty concepts by code), so a list is
    # compared as a set of entries.
    if isinstance(read, list) and isinstance(sent, list):
        return sorted(json.dumps(item, sort_keys=True) for item in read) == sorted(
            json.dumps(item, sort_keys=True) for item in sent
        )
    return read == sent


def _sent_back(case: WriteCase, sent: dict[str, object] | None, read: object) -> bool:
    """The fields the case changes read back with the values the caller sent."""
    return isinstance(read, dict) and all(
        _same_value(read.get(name), (sent or {}).get(name)) for name in case.reads_back
    )


def _refused_problems(world: World, request: Request, before: Snapshot | None) -> list[str]:
    problems: list[str] = []
    if before is not None and _read(world, request.path) != before:
        problems.append("the record changed although the write was refused")
    return problems


def _accepted_problems(
    world: World, case: WriteCase, request: Request, created_id: object
) -> list[str]:
    if case.interaction == "delete":
        after = _read(world, request.path)
        return [] if after.status == 404 else [f"the record reads {after.status} after delete"]
    record_path = request.path if created_id is None else f"/fhir/{case.resource}/{created_id}"
    after = _read(world, record_path)
    if after.status != 200 or not _sent_back(case, request.body, after.body):
        return [f"the record does not read back as sent (admin reads {after.status})"]
    return []


def _attempt(world: World, case: WriteCase, caller: Caller) -> list[str]:
    path = case.fresh(world, caller)
    before = None if case.interaction == "create" else _read(world, path)
    body = case.body(world, caller, before.body if before else None) if case.body else None
    request = Request(path, body, before.etag if before else "")
    audit_before = _audit_ids()
    rows_before = _table_ids(case.table)
    response = _send(world.clients[caller], case.interaction, request)
    status = response.status_code
    problems: list[str] = []
    expected = _expected_answer(_row_of(case), caller, case.record)
    if status != expected:
        problems.append(f"expected {expected}, got {status}")
    audit_change = _change(audit_before, _audit_ids())
    rows_change = _change(rows_before, _table_ids(case.table))
    if 200 <= status < 300:
        created_id = response.json()["id"] if case.interaction == "create" else None
        problems += _accepted_problems(world, case, request, created_id)
        expected_audit, expected_rows = (1, 0), ACCEPTED_ROWS_CHANGE[case.interaction]
    else:
        problems += _refused_problems(world, request, before)
        expected_audit, expected_rows = NO_CHANGE, NO_CHANGE
    if audit_change != expected_audit:
        problems.append(f"the audit log changed by {audit_change}, expected {expected_audit}")
    if rows_change != expected_rows:
        problems.append(f"the table changed by {rows_change}, expected {expected_rows}")
    return [f"{_label(case, caller)}: {problem}" for problem in problems]


def _walk_problems(world: World) -> list[str]:
    return [
        problem
        for case in WRITE_CASES
        for caller in Caller
        for problem in _attempt(world, case, caller)
    ]


def _coverage_problems() -> list[str]:
    write_rows = {
        (row.resource, row.interaction)
        for row in FHIR_ACCESS_ROWS
        if row.interaction in WRITE_INTERACTIONS
    }
    walked = {(case.resource, case.interaction) for case in WRITE_CASES}
    problems = [
        f"{pair} is a write row with neither a case nor a pending entry"
        for pair in sorted(write_rows - walked - NOT_WALKED_YET)
    ]
    problems += [
        f"{pair} is walked or pending but is no write row"
        for pair in sorted((walked | NOT_WALKED_YET) - write_rows)
    ]
    problems += [f"{pair} is both walked and pending" for pair in sorted(walked & NOT_WALKED_YET)]
    return problems


def returns_the_row_answer_and_the_record_state_when_each_caller_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    world = _build_world()

    assert _walk_problems(world) == []


def returns_a_case_or_a_pending_entry_for_each_write_row_when_checked() -> None:
    assert _coverage_problems() == []
