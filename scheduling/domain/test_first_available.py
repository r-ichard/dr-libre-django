"""Section 5.5: ranking candidates for first available."""

from datetime import UTC, datetime, timedelta

from scheduling.domain.first_available import Candidate, first_available, rank_candidates

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _assigned_ago(hours: int) -> datetime:
    return NOW - timedelta(hours=hours)


def returns_never_assigned_clinician_when_others_were_assigned() -> None:
    candidates = [Candidate(1, 1, _assigned_ago(1000)), Candidate(2, 1, None)]
    assert first_available(candidates, NOW) == 2


def returns_lowest_id_when_several_were_never_assigned() -> None:
    candidates = [Candidate(7, 1, None), Candidate(3, 1, None), Candidate(5, 1, None)]
    assert rank_candidates(candidates, NOW) == [3, 5, 7]


def returns_larger_idle_times_weight_when_all_were_assigned() -> None:
    candidates = [Candidate(1, 1, _assigned_ago(2)), Candidate(2, 3, _assigned_ago(1))]
    assert rank_candidates(candidates, NOW) == [2, 1]


def returns_lowest_id_when_scores_tie() -> None:
    candidates = [Candidate(9, 2, _assigned_ago(1)), Candidate(4, 1, _assigned_ago(2))]
    assert rank_candidates(candidates, NOW) == [4, 9]


def returns_none_when_no_candidate() -> None:
    assert first_available([], NOW) is None


def returns_none_when_every_candidate_has_weight_zero() -> None:
    assert first_available([Candidate(1, 0, None)], NOW) is None


def returns_clinician_with_weight_when_another_has_weight_zero() -> None:
    candidates = [Candidate(1, 0, None), Candidate(2, 1, _assigned_ago(1))]
    assert rank_candidates(candidates, NOW) == [2]
