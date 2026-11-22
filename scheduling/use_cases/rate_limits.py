"""Section 7.5: hourly counters per email address and per network address. Rows hold only a keyed
hash, so a leaked table lists no mailbox and no address, and a hash of an address cannot be
reversed without SECRET_KEY."""

import hashlib
import hmac

from django.conf import settings
from django.db import transaction

from scheduling.domain.rate_limit_rules import (
    RATE_LIMITS,
    RateLimitScope,
    is_limited,
    retry_after_seconds,
    window_start,
)
from scheduling.models import RateLimitHit
from scheduling.use_cases.advisory_lock import lock_keys
from scheduling.use_cases.request_context import current_request_context


def key_hash(kind: str, value: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def take_hit(scope: RateLimitScope, email: str | None, address: str) -> int | None:
    """Records one request and returns None, or returns the seconds until a request would pass and
    records nothing when either counter is full. The email is the normalised address; the lock makes
    check and insert one step so concurrent requests cannot overshoot."""
    now = current_request_context().now
    limit = RATE_LIMITS[scope]
    counters = [(key_hash("address", address), limit.per_address)]
    if email is not None and limit.per_email is not None:
        counters.insert(0, (key_hash("email", email), limit.per_email))
    with transaction.atomic():
        lock_keys([hashed for hashed, _maximum in counters])
        recent = RateLimitHit.objects.filter(scope=scope, hit_at__gt=window_start(now))
        waits = []
        for hashed, maximum in counters:
            times = list(
                recent.filter(key_hash=hashed).order_by("hit_at").values_list("hit_at", flat=True)
            )
            if is_limited(len(times), maximum):
                waits.append(retry_after_seconds(times, maximum, now))
        if waits:
            return max(waits)
        hits = [
            RateLimitHit(scope=scope, key_hash=hashed, hit_at=now) for hashed, _maximum in counters
        ]
        RateLimitHit.objects.bulk_create(hits)
    return None
