"""Task 09: the worker's schedule. Every job is idempotent, so a restart that runs them all on
its first tick does no harm."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from scheduling.domain.job_schedule import is_due
from scheduling.jobs.runner import Job, run_job
from scheduling.use_cases.email_delivery import send_pending_emails
from scheduling.use_cases.purge import purge_expired
from scheduling.use_cases.reminders import send_reminders
from scheduling.use_cases.waitlist_expiry import expire_waitlist

EMAIL_BATCH_SIZE = 100


@dataclass(frozen=True)
class ScheduledJob:
    job: Job
    interval: timedelta


def _purge() -> dict[str, int]:
    counts = purge_expired()
    return {
        "session_count": counts.session_count,
        "sign_in_failure_count": counts.sign_in_failure_count,
    }


SEND_REMINDERS = Job("send_reminders", lambda: {"reminder_count": send_reminders(None)})
EXPIRE_WAITLIST = Job("expire_waitlist", lambda: {"waitlist_count": expire_waitlist()})
SEND_PENDING_EMAILS = Job(
    "send_pending_emails",
    lambda: {"sent_count": send_pending_emails(EMAIL_BATCH_SIZE)},
    atomic=False,
)
PURGE_EXPIRED = Job("purge_expired", _purge)

JOB_SCHEDULE: tuple[ScheduledJob, ...] = (
    ScheduledJob(SEND_REMINDERS, timedelta(minutes=10)),
    ScheduledJob(EXPIRE_WAITLIST, timedelta(minutes=5)),
    ScheduledJob(SEND_PENDING_EMAILS, timedelta(minutes=1)),
    ScheduledJob(PURGE_EXPIRED, timedelta(hours=1)),
)


def run_due_jobs(
    schedule: list[ScheduledJob] | tuple[ScheduledJob, ...],
    last_runs: dict[str, datetime],
    now: datetime,
) -> None:
    for scheduled in schedule:
        name = scheduled.job.name
        if is_due(last_runs.get(name), scheduled.interval, now):
            # A failed run counts as a run: it is retried after its interval, not every second.
            last_runs[name] = now
            run_job(scheduled.job, now)
