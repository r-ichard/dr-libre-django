"""Section 5.5: ranking candidates for first available."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from scheduling.domain.first_available import Candidate, first_available, rank_candidates

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _assigned_ago(hours: int) -> datetime:
    return NOW - timedelta(hours=hours)


def returns_never_assigned_clinician_when_others_were_assigned() -> None:
    candidates = [Candidate(UUID(int=1), 1, _assigned_ago(1000)), Candidate(UUID(int=2), 1, None)]
    assert first_available(candidates, NOW) == UUID(int=2)


def returns_lowest_id_when_several_were_never_assigned() -> None:
    candidates = [
        Candidate(UUID(int=7), 1, None),
        Candidate(UUID(int=3), 1, None),
        Candidate(UUID(int=5), 1, None),
    ]
    assert rank_candidates(candidates, NOW) == [UUID(int=3), UUID(int=5), UUID(int=7)]


def returns_larger_idle_times_weight_when_all_were_assigned() -> None:
    candidates = [
        Candidate(UUID(int=1), 1, _assigned_ago(2)),
        Candidate(UUID(int=2), 3, _assigned_ago(1)),
    ]
    assert rank_candidates(candidates, NOW) == [UUID(int=2), UUID(int=1)]


def returns_lowest_id_when_scores_tie() -> None:
    candidates = [
        Candidate(UUID(int=9), 2, _assigned_ago(1)),
        Candidate(UUID(int=4), 1, _assigned_ago(2)),
    ]
    assert rank_candidates(candidates, NOW) == [UUID(int=4), UUID(int=9)]


def returns_none_when_no_candidate() -> None:
    assert first_available([], NOW) is None


def returns_none_when_every_candidate_has_weight_zero() -> None:
    assert first_available([Candidate(UUID(int=1), 0, None)], NOW) is None


def returns_clinician_with_weight_when_another_has_weight_zero() -> None:
    candidates = [Candidate(UUID(int=1), 0, None), Candidate(UUID(int=2), 1, _assigned_ago(1))]
    assert rank_candidates(candidates, NOW) == [UUID(int=2)]


def returns_lowest_uuid_first_when_exact_products_tie() -> None:
    # Exact products tie: 1 microsecond * 10 == 10 microseconds * 1. Floats differ by one ulp.
    low, high = UUID(int=2), UUID(int=5)
    candidates = [
        Candidate(high, 1, NOW - timedelta(microseconds=10)),
        Candidate(low, 10, NOW - timedelta(microseconds=1)),
    ]
    assert rank_candidates(candidates, NOW) == [low, high]


def returns_longer_idle_first_when_float_seconds_would_round_equal() -> None:
    # Two microseconds apart idle times that total_seconds() cannot tell apart at this magnitude.
    far_now = datetime(9000, 1, 1, tzinfo=UTC)
    first_assigned = datetime(1, 1, 2, tzinfo=UTC)
    longer_idle, shorter_idle = UUID(int=5), UUID(int=2)
    candidates = [
        Candidate(shorter_idle, 1, first_assigned + timedelta(microseconds=1)),
        Candidate(longer_idle, 1, first_assigned),
    ]
    assert rank_candidates(candidates, far_now) == [longer_idle, shorter_idle]
