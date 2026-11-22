"""Section 7.5: the hourly limits of hold, code and link requests, per email address and per network
address, over a rolling window. A network address is shared by a whole hospital Wi-Fi, so its
limit is higher."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

WINDOW = timedelta(hours=1)


class RateLimitScope(StrEnum):
    HOLD = "hold"
    CODE = "code"
    LINK = "link"
    TOKEN = "token"  # noqa: S105 - a scope name, not a secret
    SEARCH = "search"


@dataclass(frozen=True)
class RateLimit:
    per_email: int | None
    per_address: int


RATE_LIMITS: dict[RateLimitScope, RateLimit] = {
    RateLimitScope.HOLD: RateLimit(per_email=5, per_address=20),
    RateLimitScope.CODE: RateLimit(per_email=3, per_address=10),
    RateLimitScope.LINK: RateLimit(per_email=3, per_address=10),
    # Failed bearer tokens only: per presented token and per network address.
    RateLimitScope.TOKEN: RateLimit(per_email=5, per_address=20),
    # Public search has no email; callers behind one proxy share an address until task 26 item 3.
    RateLimitScope.SEARCH: RateLimit(per_email=None, per_address=120),
}


def window_start(now: datetime) -> datetime:
    return now - WINDOW


def is_limited(hits: int, limit: int) -> bool:
    return hits >= limit


SECONDS_PER_MINUTE = 60


def retry_after_seconds(hits: list[datetime], limit: int, now: datetime) -> int:
    """Seconds until a request would pass: enough of the oldest hits must leave the window that
    fewer than `limit` remain. `hits` are inside the window, oldest first. Rounded up, at least one,
    so a caller never retries too early."""
    blocking = hits[len(hits) - limit]
    seconds_left = (blocking + WINDOW - now).total_seconds()
    return max(1, math.ceil(seconds_left))


def wait_sentence(seconds: int) -> str:
    if seconds < SECONDS_PER_MINUTE:
        return f"Try again in {seconds} {'second' if seconds == 1 else 'seconds'}."
    minutes = math.ceil(seconds / SECONDS_PER_MINUTE)
    return f"Try again in {minutes} {'minute' if minutes == 1 else 'minutes'}."
