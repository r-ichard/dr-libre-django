"""Task 09: the worker's only decision, whether a job's interval has elapsed."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.job_schedule import is_due

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
TEN_MINUTES = timedelta(minutes=10)


def returns_due_when_never_run() -> None:
    assert is_due(None, TEN_MINUTES, NOW) is True


def returns_not_due_when_interval_not_elapsed() -> None:
    assert is_due(NOW - TEN_MINUTES + timedelta(seconds=1), TEN_MINUTES, NOW) is False


def returns_due_when_interval_exactly_elapsed() -> None:
    assert is_due(NOW - TEN_MINUTES, TEN_MINUTES, NOW) is True


def returns_due_when_interval_long_elapsed() -> None:
    assert is_due(NOW - timedelta(days=1), TEN_MINUTES, NOW) is True
