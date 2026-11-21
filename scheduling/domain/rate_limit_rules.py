"""Section 7.5: the hourly limits of hold, code and link requests, per email address and per network
address, over a rolling window. A network address is shared by a whole hospital Wi-Fi, so its
limit is higher."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

WINDOW = timedelta(hours=1)


class RateLimitScope(StrEnum):
    HOLD = "hold"
    CODE = "code"
    LINK = "link"


@dataclass(frozen=True)
class RateLimit:
    per_email: int
    per_address: int


RATE_LIMITS: dict[RateLimitScope, RateLimit] = {
    RateLimitScope.HOLD: RateLimit(per_email=5, per_address=20),
    RateLimitScope.CODE: RateLimit(per_email=3, per_address=10),
    RateLimitScope.LINK: RateLimit(per_email=3, per_address=10),
}


def window_start(now: datetime) -> datetime:
    return now - WINDOW


def is_limited(hits: int, limit: int) -> bool:
    return hits >= limit
