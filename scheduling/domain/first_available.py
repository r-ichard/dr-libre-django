"""Section 5.5: ranking candidates for first available."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID


@dataclass(frozen=True)
class Candidate:
    clinician_id: UUID
    weight: int
    last_assigned_at: datetime | None


def rank_candidates(candidates: list[Candidate], now: datetime) -> list[UUID]:
    weighted = [candidate for candidate in candidates if candidate.weight > 0]
    ranked = sorted(weighted, key=lambda candidate: _rank_key(candidate, now))
    return [candidate.clinician_id for candidate in ranked]


def first_available(candidates: list[Candidate], now: datetime) -> UUID | None:
    ranked = rank_candidates(candidates, now)
    return ranked[0] if ranked else None


def _rank_key(candidate: Candidate, now: datetime) -> tuple[int, int, UUID]:
    if candidate.last_assigned_at is None:
        return (0, 0, candidate.clinician_id)
    idle_microseconds = (now - candidate.last_assigned_at) // timedelta(microseconds=1)
    return (1, -idle_microseconds * candidate.weight, candidate.clinician_id)
