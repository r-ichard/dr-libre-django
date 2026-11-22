"""Section 7.5: hourly counters per email address and per network address. Rows hold only a keyed
hash, so a leaked table lists no mailbox and no address, and a hash of an address cannot be
reversed without SECRET_KEY."""

import hashlib
import hmac

from django.conf import settings
from django.db import connection, transaction

from scheduling.domain.rate_limit_rules import (
    RATE_LIMITS,
    RateLimitScope,
    is_limited,
    window_start,
)
from scheduling.models import RateLimitHit
from scheduling.use_cases.request_context import current_request_context

HASH_PREFIX_DIGITS = 16


def key_hash(kind: str, value: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def take_hit(scope: RateLimitScope, email: str, address: str) -> bool:
    """Records one request and returns True, or returns False and records nothing when either
    counter is full. The email is the normalised address; the lock makes check and insert one step
    so concurrent requests cannot overshoot."""
    now = current_request_context().now
    limit = RATE_LIMITS[scope]
    counters = (
        (key_hash("email", email), limit.per_email),
        (key_hash("address", address), limit.per_address),
    )
    with transaction.atomic():
        _lock_keys([hashed for hashed, _maximum in counters])
        recent = RateLimitHit.objects.filter(scope=scope, hit_at__gt=window_start(now))
        full = any(
            is_limited(recent.filter(key_hash=hashed).count(), maximum)
            for hashed, maximum in counters
        )
        if full:
            return False
        hits = [
            RateLimitHit(scope=scope, key_hash=hashed, hit_at=now) for hashed, _maximum in counters
        ]
        RateLimitHit.objects.bulk_create(hits)
    return True


def _lock_keys(hashes: list[str]) -> None:
    """Sorted, so two requests that share a key never wait on each other in a circle."""
    numbers = sorted(
        int.from_bytes(bytes.fromhex(hashed[:HASH_PREFIX_DIGITS]), "big", signed=True)
        for hashed in hashes
    )
    with connection.cursor() as cursor:
        for number in numbers:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [number])


def is_full(scope: RateLimitScope, email: str, address: str) -> bool:
    """True when either counter has reached its limit; records nothing."""
    limit = RATE_LIMITS[scope]
    recent = RateLimitHit.objects.filter(
        scope=scope, hit_at__gt=window_start(current_request_context().now)
    )
    return any(
        is_limited(recent.filter(key_hash=key_hash(kind, value)).count(), maximum)
        for kind, value, maximum in (
            ("email", email, limit.per_email),
            ("address", address, limit.per_address),
        )
    )


def record_hits(scope: RateLimitScope, email: str, address: str) -> None:
    """Counts one event on both counters, for scopes where only a failure counts."""
    now = current_request_context().now
    RateLimitHit.objects.bulk_create(
        RateLimitHit(scope=scope, key_hash=key_hash(kind, value), hit_at=now)
        for kind, value in (("email", email), ("address", address))
    )
