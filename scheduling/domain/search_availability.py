"""Section 6.2: which type the times are for, and the first starts over the long horizon,
looked for in chunks of the engine's 31 day cap."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import SlotType, TimeRange, free_slots
from scheduling.domain.slot_search import MAXIMUM_QUERY_DAYS, ClinicianSchedule

CHUNK = timedelta(days=MAXIMUM_QUERY_DAYS)


@dataclass(frozen=True)
class BookableType:
    id: UUID
    name: str
    duration_minutes: int
    buffer_minutes: int = 0


def shortest_type(types: Sequence[BookableType]) -> BookableType:
    return min(
        types, key=lambda candidate: (candidate.duration_minutes, candidate.name, candidate.id)
    )


def next_starts(
    schedule: ClinicianSchedule,
    slot_type: SlotType,
    window: TimeRange,
    now: datetime,
    time_zone: ZoneInfo,
    count: int,
    keep: Callable[[datetime], bool] = lambda start: True,
) -> list[datetime]:
    found: list[datetime] = []
    chunk_start = window.starts_at
    while chunk_start < window.ends_at and len(found) < count:
        chunk_end = min(chunk_start + CHUNK, window.ends_at)
        starts = free_slots(
            schedule.rules,
            slot_type,
            schedule.time_off,
            schedule.appointments,
            TimeRange(chunk_start, chunk_end),
            now,
            time_zone,
        )
        found.extend(start for start in starts if start not in found and keep(start))
        # The next chunk reaches back one duration so a slot across the border is not lost.
        chunk_start = chunk_end - slot_type.duration if chunk_end < window.ends_at else chunk_end
    return found[:count]
