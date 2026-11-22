"""One place for the Postgres advisory locks that make a count-then-write one step per key."""

from django.db import connection

HASH_PREFIX_DIGITS = 16


def lock_keys(hashes: list[str]) -> None:
    """Sorted, so two requests that share a key never wait on each other in a circle. The lock
    lasts until the surrounding transaction ends."""
    numbers = sorted(
        int.from_bytes(bytes.fromhex(hashed[:HASH_PREFIX_DIGITS]), "big", signed=True)
        for hashed in hashes
    )
    with connection.cursor() as cursor:
        for number in numbers:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [number])
