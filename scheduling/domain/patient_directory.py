"""Section 9.3: the clinician's patient list searches by name and shows last and next visit."""

from collections.abc import Sequence
from datetime import datetime


def matches_name(full_name: str, query: str) -> bool:
    haystack = full_name.casefold()
    return all(term in haystack for term in query.casefold().split())


def last_and_next_visit(
    now: datetime, visit_starts: Sequence[datetime]
) -> tuple[datetime | None, datetime | None]:
    past = [start for start in visit_starts if start <= now]
    future = [start for start in visit_starts if start > now]
    return (max(past) if past else None, min(future) if future else None)
