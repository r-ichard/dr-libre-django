"""Sections 15.2, 15.4 and 15.5: `AuditEvent` is the audit log, read by an admin only and
never written."""

import json
import re
import time
from datetime import datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.demo_seed.seed_support import run_seed, seed_environment
from scheduling.models import AuditLogEntry, User
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

__all__ = ["seed_environment"]

BULK_ENTRIES = 50_000
PAGE_SIZE = 20
# Six for the page itself and three for the read counter, fixed whatever the log holds.
MAX_PAGE_QUERIES = 9
MAX_PAGE_SECONDS = 1.0


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _entry(actor: User | None, **fields: object) -> AuditLogEntry:
    values = {
        "action": "waitlist.accept",
        "entity_type": "waitlistentry",
        "entity_id": "7d0f2c4e-0000-4000-8000-000000000001",
        "metadata": {"changed_fields": ["status"]},
        "correlation_id": "corr-24",
        **fields,
    }
    row = make("AuditLogEntry", actor=actor, **values)
    assert isinstance(row, AuditLogEntry)
    return row


def returns_action_agent_entity_details_and_correlation_id_when_admin_reads_an_entry() -> None:
    admin = make("User", role="ADMIN")
    assert isinstance(admin, User)
    row = _entry(admin)

    response = get(f"/fhir/AuditEvent/{row.pk}", token_of(admin))

    body = response.json()
    assert response.status_code == 200
    assert body["resourceType"] == "AuditEvent"
    assert (body["action"], body["type"]["code"]) == ("U", "waitlist.accept")
    assert body["agent"][0]["who"]["reference"].endswith(f"/{admin.pk}")
    assert body["entity"][0]["what"]["identifier"]["value"] == row.entity_id
    assert "status" in str(body["entity"][0]["detail"])
    assert "corr-24" in str(body["extension"])
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
def returns_403_when_a_non_admin_reads_or_searches_the_audit_trail(role: str) -> None:
    row = _entry(None)
    token = token_of(role=role)

    assert get(f"/fhir/AuditEvent/{row.pk}", token).status_code == 403
    assert get("/fhir/AuditEvent", token).status_code == 403


def returns_401_when_the_audit_trail_is_read_without_token() -> None:
    row = _entry(None)

    assert get(f"/fhir/AuditEvent/{row.pk}").status_code == 401
    assert get("/fhir/AuditEvent").status_code == 401


def returns_only_matching_events_when_admin_searches_by_action_and_entity_type() -> None:
    _entry(None)
    _entry(None, action="notification.read", entity_type="notification")

    by_action = get("/fhir/AuditEvent?type=notification.read", token_of(role="ADMIN"))
    by_type = get("/fhir/AuditEvent?entity-type=waitlistentry", token_of(role="ADMIN"))

    assert by_action.json()["total"] == 1
    assert by_type.json()["total"] == 1


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def returns_405_when_the_audit_trail_is_written(method: str) -> None:
    row = _entry(None)
    path = "/fhir/AuditEvent" if method == "post" else f"/fhir/AuditEvent/{row.pk}"

    response = send(method, path, {"resourceType": "AuditEvent"}, token_of(role="ADMIN"))

    assert response.status_code == 405


def returns_details_flattened_and_without_empty_values() -> None:
    row = _entry(
        None,
        metadata={
            "changed_fields": ["status", "reason"],
            "counts": {"rows": 3, "gone": None, "empty": []},
            "nothing": None,
            "none_listed": [],
        },
    )

    body = get(f"/fhir/AuditEvent/{row.pk}", token_of(role="ADMIN")).json()

    assert sorted(body["entity"][0]["detail"], key=lambda detail: detail["type"]) == [
        {"type": "changed_fields", "valueString": "status, reason"},
        {"type": "rows", "valueString": "3"},
    ]


def returns_the_creation_time_as_recorded() -> None:
    row = _entry(None)

    body = get(f"/fhir/AuditEvent/{row.pk}", token_of(role="ADMIN")).json()

    assert datetime.fromisoformat(body["recorded"]) == row.created_at.replace(
        microsecond=row.created_at.microsecond // 1000 * 1000
    )


def returns_only_the_actors_events_when_searching_by_agent() -> None:
    actor = make("User", role="ADMIN")
    assert isinstance(actor, User)
    mine = _entry(actor)
    _entry(None)
    other = make("User", role="ADMIN")
    assert isinstance(other, User)
    _entry(other)

    search = get(f"/fhir/AuditEvent?agent={actor.pk}", token_of(role="ADMIN")).json()

    assert [found["resource"]["id"] for found in search["entry"]] == [str(mine.pk)]


def returns_only_the_entity_of_the_given_type_and_id_when_searching_by_entity() -> None:
    wanted = _entry(None)
    _entry(None, entity_type="notification")
    _entry(None, entity_id="other-id")
    admin = token_of(role="ADMIN")

    typed = get(f"/fhir/AuditEvent?entity=waitlistentry/{wanted.entity_id}", admin).json()
    bare = get(f"/fhir/AuditEvent?entity={wanted.entity_id}", admin).json()

    assert [found["resource"]["id"] for found in typed["entry"]] == [str(wanted.pk)]
    assert bare["total"] == 2


def returns_newest_entries_first_when_no_sort_is_given() -> None:
    older = _entry(None, created_at=NOW.replace(hour=8))
    newest = _entry(None, created_at=NOW.replace(hour=10))
    middle = _entry(None, created_at=NOW.replace(hour=9))

    search = get("/fhir/AuditEvent?type=waitlist.accept", token_of(role="ADMIN")).json()

    assert [found["resource"]["id"] for found in search["entry"]] == [
        str(newest.pk),
        str(middle.pk),
        str(older.pk),
    ]


def returns_a_page_in_bounded_queries_and_time_when_the_log_holds_50000_entries() -> None:
    AuditLogEntry.objects.bulk_create(
        AuditLogEntry(
            action="waitlist.accept",
            entity_type="waitlistentry",
            entity_id=str(index),
            correlation_id="corr-bulk",
            created_at=NOW - timedelta(seconds=index),
        )
        for index in range(BULK_ENTRIES)
    )
    token = token_of(role="ADMIN")
    get("/fhir/AuditEvent?_count=20", token)

    started = time.monotonic()
    with CaptureQueriesContext(connection) as captured:
        response = get("/fhir/AuditEvent?_count=20", token)
    elapsed = time.monotonic() - started

    assert len(response.json()["entry"]) == PAGE_SIZE
    assert len(captured) <= MAX_PAGE_QUERIES
    assert elapsed < MAX_PAGE_SECONDS


def returns_no_personal_data_in_any_event_when_the_demo_seed_ran(seed_environment: None) -> None:
    run_seed()
    token = token_of(role="ADMIN")
    bodies = []
    offset = 0
    while True:
        page = get(f"/fhir/AuditEvent?_count=100&_offset={offset}", token).json()
        bodies += [found["resource"] for found in page.get("entry", [])]
        offset += 100
        if offset >= page["total"]:
            break

    text = json.dumps(bodies)
    personal = list(User.objects.values_list("email", "full_name", "phone", "date_of_birth"))
    assert len(bodies) > 0
    for email, full_name, phone, date_of_birth in personal:
        for value in (email, full_name, phone, date_of_birth):
            if value:
                assert str(value) not in text
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    assert not re.search(r'"(reason|note|notes|name)"', text)
