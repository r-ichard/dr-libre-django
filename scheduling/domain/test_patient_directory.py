"""Section 9.3: the clinician's patient list searches by name and shows last and next visit."""

from datetime import UTC, datetime, timedelta

import pytest

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


@pytest.mark.parametrize("query", ["linus", "LINKFREI", "linkfrei linus", "  li  nk "])
def returns_matches_name_when_terms_in_any_order_ignoring_case(query: str) -> None:
    from scheduling.domain.patient_directory import matches_name

    assert matches_name("Linus Linkfrei", query)


@pytest.mark.parametrize("query", ["", "   "])
def returns_matches_all_when_query_empty(query: str) -> None:
    from scheduling.domain.patient_directory import matches_name

    assert matches_name("Linus Linkfrei", query)


@pytest.mark.parametrize("query", ["linus berta", "%", "_", "x"])
def rejects_name_when_a_term_is_missing(query: str) -> None:
    from scheduling.domain.patient_directory import matches_name

    assert not matches_name("Linus Linkfrei", query)


def returns_picks_last_past_and_next_future_visit() -> None:
    from scheduling.domain.patient_directory import last_and_next_visit

    visits = [
        NOW - timedelta(days=9),
        NOW - timedelta(days=2),
        NOW + timedelta(days=3),
        NOW + timedelta(days=8),
    ]

    assert last_and_next_visit(NOW, visits) == (NOW - timedelta(days=2), NOW + timedelta(days=3))


def returns_nothing_for_missing_side() -> None:
    from scheduling.domain.patient_directory import last_and_next_visit

    assert last_and_next_visit(NOW, []) == (None, None)
