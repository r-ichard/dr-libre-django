"""A browser's datetime-local value is a wall-clock time with no zone: read it in the hospital's
zone. A time that does not exist or happens twice (clock changes) is refused, never guessed."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.failure import Failure
from scheduling.domain.request_limits import day_in_range


def utc_from_local(raw: str, zone: ZoneInfo) -> datetime | None:
    try:
        wall = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if wall.tzinfo is not None or not day_in_range(wall.date()):
        return None
    early = wall.replace(tzinfo=zone, fold=0)
    late = wall.replace(tzinfo=zone, fold=1)
    exists = early.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == wall
    if not exists or early.utcoffset() != late.utcoffset():
        return None
    return early.astimezone(UTC)


def errors_by_field(failure: Failure) -> dict[str, str]:
    """First message of each field of an invalid_input failure."""
    fields = failure.details.get("fields", [])
    found: dict[str, str] = {}
    if isinstance(fields, list):
        for item in fields:
            if isinstance(item, dict):
                found.setdefault(str(item["field"]), str(item["message"]))
    return found
