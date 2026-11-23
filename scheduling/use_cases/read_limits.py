"""Hourly counters of public reads that cost work. A signed-in caller is counted by
user id, so staff behind one network address do not use up each other's allowance."""

from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.models import User
from scheduling.use_cases.rate_limits import take_hit


def counter_key(user: User | None, address: str) -> str:
    """The `user:` prefix cannot collide with a network address."""
    return address if user is None else f"user:{user.pk}"


def take_read_hit(scope: RateLimitScope, user: User | None, address: str) -> int | None:
    """None when the read may go on, else the seconds until it may."""
    return take_hit(scope, None, counter_key(user, address))
