"""Section 9: blocks that share a column get lanes; touching blocks do not share."""


def _lanes(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    from scheduling.domain.lane_assignment import assign_lanes

    return [(each.lane, each.lane_count) for each in assign_lanes(intervals)]


def returns_empty_when_no_blocks() -> None:
    from scheduling.domain.lane_assignment import assign_lanes

    assert assign_lanes([]) == []


def returns_lane_placement_values_when_one_block() -> None:
    from scheduling.domain.lane_assignment import LanePlacement, assign_lanes

    assert assign_lanes([(3, 5)]) == [LanePlacement(lane=1, lane_count=1)]


def returns_one_lane_each_when_blocks_only_touch() -> None:
    assert _lanes([(0, 2), (2, 4)]) == [(1, 1), (1, 1)]


def returns_two_lanes_when_three_blocks_overlap_in_a_chain() -> None:
    assert _lanes([(0, 4), (2, 6), (4, 8)]) == [(1, 2), (2, 2), (1, 2)]


def returns_three_lanes_when_three_blocks_overlap_at_once() -> None:
    assert _lanes([(0, 6), (1, 6), (2, 6)]) == [(1, 3), (2, 3), (3, 3)]


def returns_separate_counts_when_clusters_are_apart() -> None:
    assert _lanes([(0, 3), (1, 4), (6, 8)]) == [(1, 2), (2, 2), (1, 1)]


def returns_input_order_when_input_is_unsorted() -> None:
    assert _lanes([(4, 8), (0, 4), (2, 6)]) == [(1, 2), (1, 2), (2, 2)]


def returns_lowest_free_lane_when_an_earlier_lane_has_ended() -> None:
    assert _lanes([(0, 2), (1, 8), (2, 4)]) == [(1, 2), (2, 2), (1, 2)]


def returns_overlap_when_two_blocks_share_the_same_single_row() -> None:
    assert _lanes([(5, 6), (5, 6)]) == [(1, 2), (2, 2)]


def returns_one_lane_per_layer_when_a_whole_day_of_time_off_covers_appointments() -> None:
    from scheduling.domain.lane_assignment import covered_by

    band = [(1, 25)]
    appointments = [(3, 4), (7, 9), (12, 13)]

    assert _lanes(band) == [(1, 1)]
    assert _lanes(appointments) == [(1, 1), (1, 1), (1, 1)]
    assert covered_by(appointments, band) == [True, True, True]


def returns_band_lane_one_and_appointment_lane_two_when_layers_are_assigned_together() -> None:
    assert _lanes([(1, 25), (3, 4), (7, 9), (12, 13)]) == [(1, 2), (2, 2), (2, 2), (2, 2)]


def returns_covered_only_for_fronts_that_overlap_a_band() -> None:
    from scheduling.domain.lane_assignment import covered_by

    assert covered_by([(0, 2), (3, 5), (8, 9)], [(4, 6)]) == [False, True, False]


def returns_not_covered_when_the_front_only_touches_the_band() -> None:
    from scheduling.domain.lane_assignment import covered_by

    assert covered_by([(0, 2), (4, 6)], [(2, 4)]) == [False, False]


def returns_not_covered_when_there_is_no_band() -> None:
    from scheduling.domain.lane_assignment import covered_by

    assert covered_by([(0, 2)], []) == [False]


def returns_covered_when_the_front_surrounds_the_band() -> None:
    from scheduling.domain.lane_assignment import covered_by

    assert covered_by([(3, 8)], [(4, 6)]) == [True]
