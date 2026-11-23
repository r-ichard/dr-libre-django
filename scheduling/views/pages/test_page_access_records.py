"""Section 12.3: a record page gives the caller's own record its row's answer. Another user's
record is refused with nothing of it shown. A missing record is 404 for an admitted caller.
Every record GET route is walked."""

from typing import Literal

import pytest
from django.test import Client

from scheduling.views.pages.page_walk_support import make_world
from scheduling.views.pages.record_walk_support import (
    Records,
    accepted_answers,
    has_other_record,
    leaks,
    other_marks,
    path_for,
    records_of,
)
from scheduling.views.pages.test_page_access_rows import Answer, Caller, Row
from scheduling.views.pages.test_page_access_table import _all_rows
from scheduling.views.pages.test_page_access_walk import (
    CALLERS,
    _answer_of,
    _answers_get,
    _clients,
    _page_callbacks,
)

pytestmark = pytest.mark.django_db

Leg = Literal["own", "other", "missing"]

# Record routes that answer no GET: their pages are reached by a form, walked by the form tests.
NO_GET_RECORD_ROUTES = frozenset(
    {
        "admin-console/appointments/<uuid:appointment_id>/check-in",
        "admin-console/appointments/<uuid:appointment_id>/complete",
        "admin-console/appointments/<uuid:appointment_id>/no-show",
        "admin-console/waitlist/<uuid:entry_id>/accept",
        "admin-console/waitlist/<uuid:entry_id>/offer",
        "book/holds/<uuid:hold_id>/resend",
        "clinician/appointments/<uuid:appointment_id>/check-in",
        "clinician/appointments/<uuid:appointment_id>/complete",
        "clinician/appointments/<uuid:appointment_id>/no-show",
        "clinician/appointments/<uuid:appointment_id>/notes",
        "patient/notifications/<uuid:notification_id>/read",
        "patient/waitlist/<uuid:entry_id>/accept",
    }
)


def _record_rows() -> list[Row]:
    return [
        row for row in _all_rows() if row.names_record and row.route not in NO_GET_RECORD_ROUTES
    ]


def _check(leg: Leg, row: Row, caller: Caller, client: Client, records: Records) -> list[str]:
    response = client.get(path_for(row.route, leg, caller, records))
    got = _answer_of(response)
    accepted = accepted_answers(leg, row, caller)
    label = f"{caller} {leg} {row.route}"
    if got not in accepted:
        return [f"{label}: want {sorted(accepted)} got {got}"]
    if (
        leg == "other"
        and got != Answer.OK
        and leaks(response.content.decode(), other_marks(records))
    ):
        return [f"{label}: shows another user's record"]
    return []


def _mismatches(leg: Leg) -> list[str]:
    world = make_world()
    clients = _clients(world)
    records = records_of(world, clients)
    found: list[str] = []
    for row in _record_rows():
        for caller in CALLERS:
            if leg == "other" and not has_other_record(row.route, caller):
                continue
            found.extend(_check(leg, row, caller, clients[caller], records))
    return found


def returns_row_answer_when_caller_gets_own_record_page() -> None:
    mismatches = _mismatches("own")
    assert mismatches == [], "\n".join(mismatches)


def returns_refusal_without_trace_when_caller_gets_other_users_record_page() -> None:
    mismatches = _mismatches("other")
    assert mismatches == [], "\n".join(mismatches)


def returns_404_or_row_answer_when_caller_gets_missing_record() -> None:
    mismatches = _mismatches("missing")
    assert mismatches == [], "\n".join(mismatches)


def returns_every_record_get_route_in_walk_when_resolver_lists_it() -> None:
    resolver_routes = {
        route
        for route, callback in _page_callbacks().items()
        if "<uuid:" in route and _answers_get(callback)
    }
    walked = {row.route for row in _record_rows()}
    missing = sorted(resolver_routes - walked)
    extra = sorted(walked - resolver_routes)
    assert missing == [] and extra == [], f"missing_from_walk={missing} extra_in_walk={extra}"
