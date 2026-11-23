"""The walk of /fhir reads and searches: each caller's status against its row, and the rule for a
personal record of another user. A known difference is asserted at the product's answer."""

from datetime import UTC, datetime

import pytest

from scheduling.views import clock
from scheduling.views.test_fhir_access_requests import (
    OTHER_USER_PATHS,
    READ_INTERACTION,
    SEARCH_INTERACTION,
    _path_of,
    _send,
)
from scheduling.views.test_fhir_access_world import World, _build_world
from test_support.fhir_access_rows import (
    FHIR_ACCESS_ROWS,
    KNOWN_DIFFERENCES,
    Caller,
    FhirAccessRow,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
WALKED_ROWS = tuple(
    row for row in FHIR_ACCESS_ROWS if row.interaction in (READ_INTERACTION, SEARCH_INTERACTION)
)
# Another user's record: no token 401, a patient or clinician token 403. Admin reads every record.
OTHER_USER_REFUSALS = {Caller.VISITOR: 401, Caller.PATIENT: 403, Caller.CLINICIAN: 403}


def _row_of(resource: str, interaction: str) -> FhirAccessRow:
    return next(
        row
        for row in FHIR_ACCESS_ROWS
        if (row.resource, row.interaction) == (resource, interaction)
    )


def _expected(row: FhirAccessRow, caller: Caller) -> int:
    for difference in KNOWN_DIFFERENCES:
        if (difference.resource, difference.interaction, difference.caller) == (
            row.resource,
            row.interaction,
            caller,
        ):
            return difference.product_answer
    return row.answer_for(caller)


def _walk_mismatches(world: World) -> list[str]:
    mismatches: list[str] = []
    for row in WALKED_ROWS:
        path = _path_of(row, world)
        for caller in Caller:
            expected = _expected(row, caller)
            got = _send(world, caller, path).status_code
            if got != expected:
                mismatches.append(f"GET {path} as {caller}: expected {expected}, got {got}")
    return mismatches


def _other_user_mismatches(world: World) -> list[str]:
    mismatches: list[str] = []
    for resource, other_path in OTHER_USER_PATHS.items():
        path = other_path(world)
        read_row = _row_of(resource, READ_INTERACTION)
        for caller in Caller:
            expected = read_row.admin if caller is Caller.ADMIN else OTHER_USER_REFUSALS[caller]
            got = _send(world, caller, path).status_code
            if got != expected:
                mismatches.append(
                    f"GET {path} (not theirs) as {caller}: expected {expected}, got {got}"
                )
    return mismatches


def _difference_problems() -> list[str]:
    problems: list[str] = []
    for difference in KNOWN_DIFFERENCES:
        row = _row_of(difference.resource, difference.interaction)
        cell = row.answer_for(difference.caller)
        label = f"{difference.resource} {difference.interaction} as {difference.caller}"
        if difference.row_answer != cell:
            problems.append(f"{label}: row_answer {difference.row_answer} is not the row's {cell}")
        if difference.product_answer == cell:
            problems.append(f"{label}: product answer {cell} is the row's, so the entry is stale")
    return problems


def returns_the_row_answer_for_each_caller_when_the_walk_reads_and_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    world = _build_world()

    assert _walk_mismatches(world) == []


def returns_401_or_403_or_admin_row_answer_when_a_caller_reads_another_users_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    world = _build_world()

    assert _other_user_mismatches(world) == []


def returns_no_problem_when_each_listed_difference_differs_from_its_row() -> None:
    assert _difference_problems() == []
