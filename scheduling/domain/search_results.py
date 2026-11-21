"""Sections 6.2 and 6.4: what a hospital or specialty result says about its providers."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GroupSummary:
    provider_count: int
    with_availability_count: int
    earliest_start: datetime | None


def summarise(first_starts: Sequence[datetime | None]) -> GroupSummary:
    present = [start for start in first_starts if start is not None]
    return GroupSummary(len(first_starts), len(present), min(present, default=None))
