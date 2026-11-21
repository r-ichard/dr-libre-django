"""Section 5.5: ranking candidates for first available."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candidate:
    clinician_id: int
    weight: int
    last_assigned_at: datetime | None


def rank_candidates(candidates: list[Candidate], now: datetime) -> list[int]:
    weighted = [candidate for candidate in candidates if candidate.weight > 0]
    ranked = sorted(weighted, key=lambda candidate: _rank_key(candidate, now))
    return [candidate.clinician_id for candidate in ranked]


def first_available(candidates: list[Candidate], now: datetime) -> int | None:
    ranked = rank_candidates(candidates, now)
    return ranked[0] if ranked else None


def _rank_key(candidate: Candidate, now: datetime) -> tuple[int, float, int]:
    if candidate.last_assigned_at is None:
        return (0, 0.0, candidate.clinician_id)
    idle_seconds = (now - candidate.last_assigned_at).total_seconds()
    return (1, -idle_seconds * candidate.weight, candidate.clinician_id)
