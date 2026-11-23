"""Section 4: each job has its own transaction, correlation id and instant, and logs one JSON
line with its counts, and a failure neither escapes nor touches the next job."""

import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.jobs.runner import Job, run_job
from scheduling.jobs.worker import JOB_SCHEDULE, ScheduledJob, run_due_jobs
from scheduling.models import AuditLogEntry, Session
from scheduling.models.builders import make
from scheduling.use_cases.purge import purge_expired
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.json_logging import JsonFormatter

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SECRET = "planted-secret-in-exception-3392"  # noqa: S105
CORRELATION_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[dict[str, object]] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == "scheduling.jobs":
            self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def job_lines() -> Iterator[list[dict[str, object]]]:
    collector = _Collector()
    logger = logging.getLogger("scheduling.jobs")
    previous_level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.INFO)
    try:
        yield collector.lines
    finally:
        logger.removeHandler(collector)
        logger.setLevel(previous_level)


def _counting(counts: dict[str, int]) -> Job:
    return Job("counting_job", lambda: counts)


def _failing() -> Job:
    def fail() -> dict[str, int]:
        raise RuntimeError(SECRET)

    return Job("failing_job", fail)


def returns_counts_when_job_succeeds() -> None:
    assert run_job(_counting({"reminder_count": 3}), NOW) == {"reminder_count": 3}


def returns_one_json_line_with_job_counts_and_correlation_id(
    job_lines: list[dict[str, object]],
) -> None:
    run_job(_counting({"reminder_count": 3}), NOW)

    assert len(job_lines) == 1
    line = job_lines[0]
    assert line["job"] == "counting_job"
    assert line["counts"] == {"reminder_count": 3}
    assert line["level"] == "INFO"
    assert re.fullmatch(CORRELATION_ID_PATTERN, str(line["correlation_id"]))


def returns_distinct_correlation_ids_when_the_job_runs_twice(
    job_lines: list[dict[str, object]],
) -> None:
    run_job(_counting({}), NOW)
    run_job(_counting({}), NOW)

    assert job_lines[0]["correlation_id"] != job_lines[1]["correlation_id"]


def returns_run_instant_as_request_context_now() -> None:
    seen: list[datetime] = []

    def record_now() -> dict[str, int]:
        seen.append(current_request_context().now)
        return {}

    run_job(Job("clock_job", record_now), NOW)

    assert seen == [NOW]


def returns_none_and_logs_the_failure_when_job_raises(job_lines: list[dict[str, object]]) -> None:
    result = run_job(_failing(), NOW)

    assert result is None
    assert len(job_lines) == 1
    assert job_lines[0]["level"] == "ERROR"
    assert job_lines[0]["job"] == "failing_job"
    assert job_lines[0]["exception"]["type"] == "RuntimeError"  # type: ignore[index]
    assert SECRET not in json.dumps(job_lines)


def returns_writes_rolled_back_when_job_raises() -> None:
    def write_then_fail() -> dict[str, int]:
        make("Session")
        raise RuntimeError("after the write")

    run_job(Job("rollback_job", write_then_fail), NOW)

    assert Session.objects.count() == 0


def returns_audit_entry_with_the_job_correlation_id_when_job_audits(
    job_lines: list[dict[str, object]],
) -> None:
    def audit_something() -> dict[str, int]:
        make("Session", expires_at=NOW - timedelta(seconds=1))
        purge_expired()
        return {}

    run_job(Job("audit_job", audit_something), NOW)

    audit = AuditLogEntry.objects.get(action="housekeeping.purge")
    assert audit.correlation_id == job_lines[0]["correlation_id"]
    assert audit.created_at == NOW


# --- worker ---


def _recording(calls: list[str], name: str, interval: timedelta) -> ScheduledJob:
    def run() -> dict[str, int]:
        calls.append(name)
        return {}

    return ScheduledJob(Job(name, run), interval)


def returns_every_job_run_when_first_tick() -> None:
    calls: list[str] = []
    schedule = [
        _recording(calls, "fast", timedelta(minutes=1)),
        _recording(calls, "slow", timedelta(hours=1)),
    ]

    run_due_jobs(schedule, {}, NOW)

    assert calls == ["fast", "slow"]


def returns_only_elapsed_jobs_run_when_later_tick() -> None:
    calls: list[str] = []
    schedule = [
        _recording(calls, "fast", timedelta(minutes=1)),
        _recording(calls, "slow", timedelta(hours=1)),
    ]
    last_runs: dict[str, datetime] = {}
    run_due_jobs(schedule, last_runs, NOW)
    calls.clear()

    run_due_jobs(schedule, last_runs, NOW + timedelta(seconds=59))
    run_due_jobs(schedule, last_runs, NOW + timedelta(minutes=1))

    assert calls == ["fast"]


def returns_next_job_run_when_an_earlier_job_fails() -> None:
    calls: list[str] = []
    schedule = [
        ScheduledJob(_failing(), timedelta(minutes=1)),
        _recording(calls, "after", timedelta(minutes=1)),
    ]

    run_due_jobs(schedule, {}, NOW)

    assert calls == ["after"]


def returns_failed_job_retried_only_after_its_interval() -> None:
    attempts: list[int] = []

    def fail() -> dict[str, int]:
        attempts.append(1)
        raise RuntimeError("boom")

    schedule = [ScheduledJob(Job("flaky", fail), timedelta(minutes=5))]
    last_runs: dict[str, datetime] = {}

    run_due_jobs(schedule, last_runs, NOW)
    run_due_jobs(schedule, last_runs, NOW + timedelta(minutes=1))
    run_due_jobs(schedule, last_runs, NOW + timedelta(minutes=5))

    assert len(attempts) == 2


def returns_the_documented_interval_for_each_job() -> None:
    intervals = {scheduled.job.name: scheduled.interval for scheduled in JOB_SCHEDULE}

    assert intervals == {
        "send_reminders": timedelta(minutes=10),
        "expire_waitlist": timedelta(minutes=5),
        "send_pending_emails": timedelta(minutes=1),
        "purge_expired": timedelta(hours=1),
        "expire_booking_holds": timedelta(minutes=1),
    }


def returns_email_job_without_outer_transaction_in_the_schedule() -> None:
    atomic_by_name = {scheduled.job.name: scheduled.job.atomic for scheduled in JOB_SCHEDULE}

    assert atomic_by_name["send_pending_emails"] is False
    assert atomic_by_name["send_reminders"] is True
