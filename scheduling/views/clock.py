from datetime import UTC, datetime


def now_utc() -> datetime:
    """The only wall-clock read; the middleware calls it once per request."""
    return datetime.now(UTC)
