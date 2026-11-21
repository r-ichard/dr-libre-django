import os
import time
from uuid import UUID

VERSION_7 = 7
RANDOM_BITS = 74
RANDOM_BYTES = 10


def new_identifier() -> UUID:
    """UUIDv7 (RFC 9562): a millisecond timestamp first, so identifiers sort by creation time.
    Python 3.13 has no uuid7 and PostgreSQL 15 has no uuidv7(), so it is laid out here."""
    milliseconds = time.time_ns() // 1_000_000
    random_part = int.from_bytes(os.urandom(RANDOM_BYTES)) & ((1 << RANDOM_BITS) - 1)
    random_high = random_part >> 62
    random_low = random_part & ((1 << 62) - 1)
    value = (
        (milliseconds << 80) | (VERSION_7 << 76) | (random_high << 64) | (0b10 << 62) | random_low
    )
    return UUID(int=value)
