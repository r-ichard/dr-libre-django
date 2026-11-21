"""Section 7.1 steps 3 and 4: how long a hold and a code live and when a code stops working."""

from datetime import datetime, timedelta

HOLD_LIFETIME = timedelta(minutes=10)
CODE_LIFETIME = timedelta(minutes=10)
MAXIMUM_ATTEMPTS = 5
CODE_DIGITS = 6


def code_is_usable(expires_at: datetime, attempts_used: int, now: datetime) -> bool:
    return now < expires_at and attempts_used < MAXIMUM_ATTEMPTS
