"""Task 15: the waitlist form speaks days, the use case speaks instants."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.date_words import day_label
from scheduling.domain.failure import Failure, FieldMessage, Result, Success


def window_instants(
    earliest_day: date, latest_day: date, zone: ZoneInfo
) -> Result[tuple[datetime, datetime]]:
    if latest_day < earliest_day:
        message = "The last day cannot be before the first day."
        return Failure.invalid_input([FieldMessage("latest_day", message)])
    return Success((_midnight(earliest_day, zone), _midnight(latest_day + timedelta(days=1), zone)))


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time(), tzinfo=zone).astimezone(UTC)


def window_words(earliest_at: datetime, latest_at: datetime, zone: ZoneInfo) -> str:
    """The days a window covers, as a person reads them. The end instant is exclusive, so the
    last day is the one that holds the moment just before it."""
    first_day = earliest_at.astimezone(zone).date()
    last_day = max(first_day, (latest_at.astimezone(zone) - timedelta(microseconds=1)).date())
    days = day_label(first_day)
    if last_day != first_day:
        days = f"from {days} to {day_label(last_day)}"
    return f"{days} ({zone.key})"
