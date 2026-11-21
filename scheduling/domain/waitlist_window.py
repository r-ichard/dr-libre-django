"""Task 15: the waitlist form speaks days, the use case speaks instants."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

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
