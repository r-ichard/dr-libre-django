"""Task 17f: blocks that share a column of the time grid get side by side lanes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LanePlacement:
    lane: int
    lane_count: int


def _overlaps(first: tuple[int, int], second: tuple[int, int]) -> bool:
    """Touching spans (one ends when the next starts) do not overlap."""
    return first[0] < second[1] and second[0] < first[1]


def _clusters(intervals: list[tuple[int, int]]) -> list[list[int]]:
    """Indices grouped into runs of chained overlaps, each run in start order."""
    clusters: list[list[int]] = []
    for index in sorted(range(len(intervals)), key=lambda each: intervals[each]):
        if clusters and intervals[index][0] < max(intervals[each][1] for each in clusters[-1]):
            clusters[-1].append(index)
        else:
            clusters.append([index])
    return clusters


def _lowest_free_lanes(cluster: list[int], intervals: list[tuple[int, int]]) -> list[int]:
    lane_ends: list[int] = []
    lanes: list[int] = []
    for index in cluster:
        start, end = intervals[index]
        free = next((lane for lane, ended in enumerate(lane_ends) if ended <= start), None)
        if free is None:
            lane_ends.append(end)
            free = len(lane_ends) - 1
        else:
            lane_ends[free] = end
        lanes.append(free + 1)
    return lanes


def assign_lanes(intervals: list[tuple[int, int]]) -> list[LanePlacement]:
    """Per interval (start row, end row), in input order: the lowest lane free at its start and
    the lanes its cluster of chained overlaps needs."""
    placements: dict[int, LanePlacement] = {}
    for cluster in _clusters(intervals):
        lanes = _lowest_free_lanes(cluster, intervals)
        for position, index in enumerate(cluster):
            placements[index] = LanePlacement(lanes[position], max(lanes))
    return [placements[index] for index in range(len(intervals))]


def covered_by(fronts: list[tuple[int, int]], behinds: list[tuple[int, int]]) -> list[bool]:
    """Per front interval: whether any interval behind it overlaps it."""
    return [any(_overlaps(front, behind) for behind in behinds) for front in fronts]
