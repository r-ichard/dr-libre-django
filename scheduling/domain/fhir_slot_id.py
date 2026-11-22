"""Task 23, spec 15.6: a slot id is `<schedule>.<type>.<minutes>`: the rule and the type as
26 letters of lower-case base32 of the UUID bytes, the start as minutes since the Unix epoch.
Stable, and it tells nothing beyond those three."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
PART_LENGTH = 26
PADDING = "=" * 6
MAXIMUM_MINUTE_DIGITS = 10


def slot_id(rule_id: UUID, type_id: UUID, start: datetime) -> str:
    minutes = int(start.timestamp() // 60)
    return f"{_encode(rule_id)}.{_encode(type_id)}.{minutes}"


def parse_slot_id(text: str) -> tuple[UUID, UUID, datetime] | None:
    """None for anything that is not exactly what `slot_id` builds."""
    parts = text.split(".")
    if len(parts) != 3:
        return None
    rule_id, type_id = _decode(parts[0]), _decode(parts[1])
    start = _start_of(parts[2])
    if rule_id is None or type_id is None or start is None:
        return None
    return rule_id, type_id, start


def _encode(identifier: UUID) -> str:
    return base64.b32encode(identifier.bytes).decode("ascii").rstrip("=").lower()


def _decode(text: str) -> UUID | None:
    if len(text) != PART_LENGTH:
        return None
    try:
        identifier = UUID(bytes=base64.b32decode(text.upper() + PADDING))
    except ValueError:
        return None
    return identifier if _encode(identifier) == text else None


def _start_of(text: str) -> datetime | None:
    if not (text.isascii() and text.isdigit()) or len(text) > MAXIMUM_MINUTE_DIGITS:
        return None
    if str(int(text)) != text:
        return None
    try:
        return EPOCH + timedelta(minutes=int(text))
    except OverflowError:
        return None
