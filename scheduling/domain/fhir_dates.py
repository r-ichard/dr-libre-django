"""Task 23, spec 15.5: a `date` search value with its prefix (`eq`, `ge`, `gt`, `le`, `lt`),
normalised once at the edge and read back as the half-open range it names."""

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

PREFIXES = ("eq", "ge", "gt", "le", "lt")
DEFAULT_PREFIX = "eq"
VALUE_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:\d{2})?)?"
)
DAY_LENGTH = 10
PRECISION = timedelta(seconds=1)

type Bounds = tuple[datetime | None, datetime | None]


def normalised_date(text: str) -> str | None:
    """`<prefix><day>` or `<prefix><UTC instant>`, or None when the text is not a FHIR date."""
    prefix = text[:2] if text[:2] in PREFIXES else DEFAULT_PREFIX
    body = text[2:] if text[:2] in PREFIXES else text
    if VALUE_PATTERN.fullmatch(body) is None:
        return None
    try:
        if len(body) == DAY_LENGTH:
            return f"{prefix}{date.fromisoformat(body).isoformat()}"
        moment = datetime.fromisoformat(body)
        instant = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return f"{prefix}{instant.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    except (ValueError, OverflowError):
        return None


def bounds_of(value: str) -> Bounds:
    """Half-open range `[low, high)` a normalised value asks for; None is open."""
    prefix, body = value[:2], value[2:]
    if len(body) == DAY_LENGTH:
        low = datetime.fromisoformat(body).replace(tzinfo=UTC)
        high = low + timedelta(days=1)
    else:
        low = datetime.fromisoformat(body)
        high = low + PRECISION
    return {
        "eq": (low, high),
        "ge": (low, None),
        "gt": (high, None),
        "le": (None, high),
        "lt": (None, low),
    }[prefix]


def combined_bounds(values: Sequence[str]) -> Bounds:
    lows = [low for low, _ in map(bounds_of, values) if low is not None]
    highs = [high for _, high in map(bounds_of, values) if high is not None]
    return (max(lows) if lows else None, min(highs) if highs else None)


def day_bounds(values: Sequence[str]) -> tuple[date | None, date | None]:
    """The first and last calendar day (UTC) of the combined range, both included."""
    low, high = combined_bounds(values)
    last = None if high is None else (high - timedelta(microseconds=1)).date()
    return (None if low is None else low.date(), last)


def bounded_window(values: Sequence[str], maximum: timedelta) -> tuple[datetime, datetime] | None:
    """The range the values name, or None when it is open, empty or longer than `maximum`."""
    low, high = combined_bounds(values)
    if low is None or high is None or high <= low or high - low > maximum:
        return None
    return low, high
