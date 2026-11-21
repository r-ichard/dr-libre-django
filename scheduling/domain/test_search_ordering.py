"""Section 6.4 and 6.5: sorting over the whole set, then the page is cut."""

from datetime import UTC, datetime
from uuid import UUID

from scheduling.domain.search_ordering import (
    Sortable,
    haversine_kilometres,
    paginate,
    sort_results,
)

EARLY = datetime(2030, 1, 7, 9, 0, tzinfo=UTC)
LATE = datetime(2030, 1, 9, 9, 0, tzinfo=UTC)


def _item(
    number: int, name: str, first_start: datetime | None, distance: float | None = None
) -> Sortable:
    return Sortable(UUID(int=number), name, first_start, distance)


def _names(items: list[Sortable]) -> list[str]:
    return [item.name for item in items]


def returns_soonest_first_when_sort_is_soonest() -> None:
    items = [_item(1, "A", LATE), _item(2, "B", EARLY)]

    assert _names(sort_results(items, "soonest")) == ["B", "A"]


def returns_results_without_a_slot_last_when_sort_is_soonest() -> None:
    items = [_item(1, "Aaron", None), _item(2, "Zed", LATE), _item(3, "Bea", EARLY)]

    assert _names(sort_results(items, "soonest")) == ["Bea", "Zed", "Aaron"]


def returns_name_then_id_when_first_starts_tie() -> None:
    items = [_item(3, "Bea", EARLY), _item(2, "Bea", EARLY), _item(1, "Ann", EARLY)]

    result = sort_results(items, "soonest")

    assert [(item.name, item.id.int) for item in result] == [("Ann", 1), ("Bea", 2), ("Bea", 3)]


def returns_names_without_a_slot_ordered_by_name_then_id() -> None:
    items = [_item(5, "Cy", None), _item(4, "Cy", None), _item(6, "Al", None)]

    result = sort_results(items, "soonest")

    assert [(item.name, item.id.int) for item in result] == [("Al", 6), ("Cy", 4), ("Cy", 5)]


def returns_names_a_to_z_ignoring_case_and_availability() -> None:
    items = [_item(1, "bea", EARLY), _item(2, "Ann", None), _item(3, "Cy", LATE)]

    assert _names(sort_results(items, "name_asc")) == ["Ann", "bea", "Cy"]


def returns_names_z_to_a_ignoring_case_and_availability() -> None:
    items = [_item(1, "bea", EARLY), _item(2, "Ann", None), _item(3, "Cy", LATE)]

    assert _names(sort_results(items, "name_desc")) == ["Cy", "bea", "Ann"]


def returns_ids_ascending_when_names_tie_in_z_to_a() -> None:
    items = [_item(2, "Bea", None), _item(1, "Bea", None)]

    result = sort_results(items, "name_desc")

    assert [item.id.int for item in result] == [1, 2]


def returns_nearest_first_with_missing_distance_last_when_sort_is_distance() -> None:
    items = [
        _item(1, "Far", EARLY, 80.0),
        _item(2, "Unknown", EARLY, None),
        _item(3, "Near", LATE, 2.5),
    ]

    assert _names(sort_results(items, "distance")) == ["Near", "Far", "Unknown"]


def returns_name_then_id_when_distances_tie() -> None:
    items = [_item(2, "Bea", EARLY, 5.0), _item(1, "Ann", EARLY, 5.0)]

    assert _names(sort_results(items, "distance")) == ["Ann", "Bea"]


def returns_zero_kilometres_when_points_are_equal() -> None:
    assert haversine_kilometres(52.52, 13.405, 52.52, 13.405) == 0.0


def returns_about_878_kilometres_between_berlin_and_paris() -> None:
    distance = haversine_kilometres(52.5200, 13.4050, 48.8566, 2.3522)

    assert 876.0 < distance < 880.0


def returns_one_degree_of_latitude_as_about_111_kilometres() -> None:
    assert 111.0 < haversine_kilometres(0.0, 0.0, 1.0, 0.0) < 111.4


def returns_three_pages_when_total_is_45_and_size_is_20() -> None:
    page = paginate(list(range(45)), page=1, page_size=20)

    assert (page.total, page.page_count, page.page, len(page.items)) == (45, 3, 1, 20)


def returns_the_last_page_when_page_is_9_of_3() -> None:
    page = paginate(list(range(45)), page=9, page_size=20)

    assert (page.page, page.items) == (3, [40, 41, 42, 43, 44])


def returns_page_1_of_1_when_there_are_no_items() -> None:
    page = paginate(list[int](), page=4, page_size=20)

    assert (page.total, page.page, page.page_count, page.items) == (0, 1, 1, [])


def returns_one_page_when_total_equals_the_size() -> None:
    page = paginate(list(range(20)), page=2, page_size=20)

    assert (page.page_count, page.page, len(page.items)) == (1, 1, 20)


def returns_two_pages_when_total_is_one_more_than_the_size() -> None:
    page = paginate(list(range(21)), page=2, page_size=20)

    assert (page.page_count, page.items) == (2, [20])


def returns_the_second_slice_when_page_is_2() -> None:
    page = paginate(list(range(45)), page=2, page_size=10)

    assert page.items == list(range(10, 20))


def returns_a_zero_distance_before_a_positive_one_when_sort_is_distance() -> None:
    items = [_item(1, "Away", EARLY, 0.5), _item(2, "Here", EARLY, 0.0)]

    assert _names(sort_results(items, "distance")) == ["Here", "Away"]
