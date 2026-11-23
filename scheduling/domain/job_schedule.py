"""The worker's only decision: whether a job's interval has elapsed."""

from datetime import datetime, timedelta


def is_due(last_run_at: datetime | None, interval: timedelta, now: datetime) -> bool:
    return last_run_at is None or now - last_run_at >= interval
