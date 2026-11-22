"""Task 20, items 9, 10 and 12: the read-only audit list, and its speed on a log of 50 000."""

import re
import time
from datetime import UTC, datetime
from uuid import UUID

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.audit_labels import AUDIT_LABELS
from scheduling.models import AuditLogEntry
from scheduling.models.builders import make
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

PATH = "/admin-console/audit"
PAGE_SIZE = 20
LOG_SIZE = 50_000
TIME_BUDGET_SECONDS = 1.0
FIRST = datetime(2030, 1, 1, tzinfo=UTC)


def _fill(count: int, actor_id: UUID | None = None) -> None:
    """One INSERT ... generate_series: a row at a time would eat the suite's time budget."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO scheduling_auditlogentry (id, created_at, actor_id, action, entity_type,"
            " entity_id, metadata, correlation_id, version, updated_at)"
            " SELECT gen_random_uuid(), %s + (n || ' seconds')::interval, %s, 'appointment.book',"
            " 'Appointment', n::text, '{\"secret\": \"hidden-metadata\"}'::jsonb,"
            " 'corr-' || n, 1, now()"
            " FROM generate_series(1, %s) AS n",
            [FIRST, actor_id, count],
        )


def returns_twenty_rows_newest_first_with_the_total_when_the_log_is_opened() -> None:
    _fill(45)

    html = admin_client().get(PATH).content.decode()

    assert "45 entries" in html
    assert html.count("corr-") == PAGE_SIZE
    assert html.index("corr-45") < html.index("corr-26")


def returns_plain_words_with_the_code_and_no_metadata_when_the_log_is_opened() -> None:
    _fill(1)

    html = admin_client().get(PATH).content.decode()

    assert f"{AUDIT_LABELS['appointment.book']} (appointment.book)" in html
    assert "hidden-metadata" not in html


def returns_the_last_page_when_the_page_is_past_the_end() -> None:
    _fill(25)

    html = admin_client().get(f"{PATH}?page=99").content.decode()

    assert html.count("corr-") == 5


def returns_the_default_log_when_the_filters_are_unusable() -> None:
    _fill(3)

    response = admin_client().get(f"{PATH}?entity_type=Nope&from=zz&to=2030-99-99&page=abc")

    assert response.status_code == 200 and "3 entries" in response.content.decode()


def returns_only_the_entity_type_asked_when_filtered() -> None:
    _fill(2)
    make("AuditLogEntry", entity_type="Hospital", action="hospital.create", correlation_id="only")

    html = admin_client().get(f"{PATH}?entity_type=Hospital").content.decode()

    assert "1 entry" in html and "only" in html


def returns_only_the_actor_asked_when_filtered() -> None:
    mine, other = make("User", role="ADMIN"), make("User", role="ADMIN")
    make("AuditLogEntry", actor=mine, correlation_id="from-mine")
    make("AuditLogEntry", actor=other, correlation_id="from-other")

    html = admin_client().get(f"{PATH}?actor={mine.pk}").content.decode()

    assert "from-mine" in html and "from-other" not in html


def returns_whole_days_when_the_range_starts_and_ends_on_the_edges() -> None:
    edges = {
        "before-start": datetime(2030, 1, 9, 23, 59, 59, tzinfo=UTC),
        "at-start": datetime(2030, 1, 10, 0, 0, tzinfo=UTC),
        "at-end": datetime(2030, 1, 10, 23, 59, 59, tzinfo=UTC),
        "after-end": datetime(2030, 1, 11, 0, 0, tzinfo=UTC),
    }
    for name, moment in edges.items():
        make("AuditLogEntry", created_at=moment, correlation_id=name)

    html = admin_client().get(f"{PATH}?from=2030-01-10&to=2030-01-10").content.decode()

    assert "at-start" in html and "at-end" in html
    assert "before-start" not in html and "after-end" not in html


def returns_the_default_log_when_the_range_is_reversed() -> None:
    _fill(3)

    html = admin_client().get(f"{PATH}?from=2030-01-10&to=2030-01-05").content.decode()

    assert "3 entries" in html


def returns_the_first_page_when_the_page_number_has_too_many_digits() -> None:
    _fill(25)

    html = admin_client().get(f"{PATH}?page={'9' * 7}").content.decode()

    assert html.count("corr-") == PAGE_SIZE


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def returns_405_when_the_log_route_is_asked_to_change_something(method: str) -> None:
    client = admin_client()
    _fill(1)

    response = getattr(client, method)(PATH)

    assert response.status_code == 405
    assert AuditLogEntry.objects.count() == 1


def returns_no_store_headers_and_a_get_form_only_when_the_log_is_opened() -> None:
    response = admin_client().get(PATH)

    html = response.content.decode()
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    assert 'method="post"' not in html.lower().replace('<form method="post" action="/sign-out"', "")
    assert "<script" not in html.replace('src="/static', "")


def returns_the_post_refusal_with_the_csrf_flow_of_a_browser_when_posting_to_the_log() -> None:
    assert admin_post(admin_client(), PATH, {}).status_code == 405


def returns_every_page_inside_the_budget_and_two_queries_when_the_log_holds_50000() -> None:
    admin = admin_client()
    _fill(LOG_SIZE)
    pages = (1, LOG_SIZE // PAGE_SIZE // 2, LOG_SIZE // PAGE_SIZE)

    for number in pages:
        started = time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = admin.get(f"{PATH}?page={number}&entity_type=Appointment")
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        assert elapsed < TIME_BUDGET_SECONDS
        audit_queries = [q for q in queries if "scheduling_auditlogentry" in q["sql"]]
        assert len(audit_queries) == 2
        assert not any('"metadata"' in q["sql"] and "LIMIT 20 OFFSET" in q["sql"]
                       and "IN (" not in q["sql"] for q in audit_queries)  # fmt: skip


def returns_an_index_walk_for_the_page_query_when_the_log_holds_50000() -> None:
    _fill(LOG_SIZE)
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE scheduling_auditlogentry")
        cursor.execute(
            "EXPLAIN SELECT id FROM scheduling_auditlogentry"
            " ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 40000"
        )
        plan = "\n".join(row[0] for row in cursor.fetchall())

    assert re.search(r"Index (Only )?Scan", plan), plan
