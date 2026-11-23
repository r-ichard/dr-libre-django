"""The walk over the routes that name no record: each caller's answer to each route, checked against
its access row. A pair the product answers differently is listed in KNOWN_DIFFERENCES, and the walk
asserts the product's answer for it."""

from datetime import UTC, datetime

import pytest

from scheduling.views import clock
from scheduling.views.test_api_access_requests import SENDERS
from scheduling.views.test_api_access_rows import (
    API_ACCESS_ROWS,
    KNOWN_DIFFERENCES,
    AccessRow,
    Caller,
)
from scheduling.views.test_api_access_world import World, _build_world

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOLD_ROUTE_PREFIX = "api/v1/booking/holds"


def _names_no_record(row: AccessRow) -> bool:
    return "<" not in row.route and not row.route.startswith(HOLD_ROUTE_PREFIX)


WALKED_ROWS = tuple(row for row in API_ACCESS_ROWS if _names_no_record(row))


def _expected_status(row: AccessRow, caller: Caller) -> int:
    for difference in KNOWN_DIFFERENCES:
        if (difference.caller, difference.method, difference.route) == (
            caller,
            row.method,
            row.route,
        ):
            return difference.product_answer
    return row.answer_for(caller)


def _walk_mismatches(world: World) -> list[str]:
    mismatches: list[str] = []
    for row in WALKED_ROWS:
        sender = SENDERS[(row.method, row.route)]
        for caller in Caller:
            expected = _expected_status(row, caller)
            got = sender(world, caller).status_code
            if got != expected:
                mismatches.append(
                    f"{row.method} {row.route} as {caller}: expected {expected}, got {got}"
                )
    return mismatches


def _difference_problems() -> list[str]:
    problems: list[str] = []
    for difference in KNOWN_DIFFERENCES:
        if difference.record is not None:
            continue
        row = next(
            (
                candidate
                for candidate in WALKED_ROWS
                if (candidate.method, candidate.route) == (difference.method, difference.route)
            ),
            None,
        )
        if row is None:
            problems.append(f"{difference.method} {difference.route}: not a walked row")
            continue
        cell = row.answer_for(difference.caller)
        if difference.row_answer != cell:
            problems.append(
                f"{difference.method} {difference.route} as {difference.caller}: "
                f"row_answer {difference.row_answer} is not the row's {cell}"
            )
        if difference.product_answer == cell:
            problems.append(
                f"{difference.method} {difference.route} as {difference.caller}: "
                f"product answer {cell} is the row's, so the entry is stale"
            )
    return problems


def returns_the_row_answer_for_each_caller_when_the_walk_sends_each_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)
    world = _build_world()

    problems = _difference_problems() + _walk_mismatches(world)

    assert problems == []
