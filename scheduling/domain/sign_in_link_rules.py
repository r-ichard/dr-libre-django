"""Section 7.3: a sign-in link works for 15 minutes and once, unless a newer link cancelled it."""

from datetime import datetime, timedelta

LINK_LIFETIME = timedelta(minutes=15)
TOKEN_BYTES = 32


def link_is_usable(
    now: datetime, expires_at: datetime, used_at: datetime | None, cancelled_at: datetime | None
) -> bool:
    return used_at is None and cancelled_at is None and now < expires_at
