"""Why a start of a clinician's grid is not free, spec 15.5. Time off first, then an
appointment (its buffer applied), then a booking hold; none of them means the start is free."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from scheduling.domain.free_slots import BusyInterval

BUSY_UNAVAILABLE = "busy-unavailable"
BUSY = "busy"
BUSY_TENTATIVE = "busy-tentative"
FREE = "free"
BUSY_STATUSES = (BUSY, BUSY_TENTATIVE, BUSY_UNAVAILABLE)


def busy_status(
    start: datetime,
    duration: timedelta,
    buffer: timedelta,
    time_off: Sequence[BusyInterval],
    appointments: Sequence[BusyInterval],
    holds: Sequence[BusyInterval],
) -> str | None:
    end = start + duration
    if _overlaps(start, end, time_off, timedelta(0)):
        return BUSY_UNAVAILABLE
    if _overlaps(start, end, appointments, buffer):
        return BUSY
    if _overlaps(start, end, holds, buffer):
        return BUSY_TENTATIVE
    return None


def _overlaps(
    start: datetime, end: datetime, blocks: Sequence[BusyInterval], buffer: timedelta
) -> bool:
    return any(start < block.ends_at + buffer and block.starts_at < end for block in blocks)
