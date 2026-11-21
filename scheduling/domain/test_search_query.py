"""Section 6.3 to 6.5 and 4: the address of a search never fails, an unusable value defaults."""

from datetime import date
from uuid import uuid4

from scheduling.domain.search_query import Location, SearchQuery, parse_search_query

HOSPITAL_ID = uuid4()


def returns_defaults_when_every_value_is_unusable() -> None:
    raw = {
        "q": "",
        "specialty": "nope",
        "hospital": "nope",
        "appointment_type": "nope",
        "from": "yesterday",
        "window": "fortnight",
        "time_of_day": "midnight",
        "sort": "random",
        "page": "x",
        "page_size": "x",
        "latitude": "x",
        "longitude": "x",
    }

    query = parse_search_query(raw)

    assert query == SearchQuery(
        text="",
        specialty_id=None,
        hospital_id=None,
        city=None,
        appointment_type_id=None,
        earliest_date=None,
        window="any",
        time_of_day=None,
        sort="soonest",
        page=1,
        page_size=20,
        location=None,
    )


def returns_defaults_when_no_value_is_given() -> None:
    assert parse_search_query({}) == parse_search_query({"q": "", "page": "1", "page_size": "20"})


def returns_size_20_when_size_is_25() -> None:
    assert parse_search_query({"page_size": "25"}).page_size == 20


def returns_size_10_and_50_when_size_is_one_of_the_choices() -> None:
    sizes = [parse_search_query({"page_size": value}).page_size for value in ("10", "50")]

    assert sizes == [10, 50]


def returns_page_1_when_page_is_zero_negative_or_text() -> None:
    pages = [parse_search_query({"page": value}).page for value in ("0", "-3", "two")]

    assert pages == [1, 1, 1]


def returns_the_page_when_page_is_a_positive_number() -> None:
    assert parse_search_query({"page": "7"}).page == 7


def returns_soonest_when_sort_is_distance_without_location() -> None:
    assert parse_search_query({"sort": "distance"}).sort == "soonest"


def returns_distance_when_location_given() -> None:
    query = parse_search_query({"sort": "distance", "latitude": "52.5", "longitude": "13.4"})

    assert (query.sort, query.location) == ("distance", Location(52.5, 13.4))


def returns_no_location_when_only_one_coordinate_is_given() -> None:
    assert parse_search_query({"latitude": "52.5"}).location is None


def returns_no_location_when_latitude_is_91_or_nan() -> None:
    locations = [
        parse_search_query({"latitude": latitude, "longitude": "10"}).location
        for latitude in ("91", "-91", "nan", "inf")
    ]

    assert locations == [None, None, None, None]


def returns_no_location_when_longitude_is_181() -> None:
    assert parse_search_query({"latitude": "10", "longitude": "181"}).location is None


def returns_location_when_coordinates_are_on_the_limits() -> None:
    query = parse_search_query({"latitude": "-90", "longitude": "180"})

    assert query.location == Location(-90.0, 180.0)


def returns_the_ids_when_uuids_are_well_formed() -> None:
    query = parse_search_query({"hospital": str(HOSPITAL_ID)})

    assert query.hospital_id == HOSPITAL_ID


def returns_no_filter_when_uuid_is_malformed() -> None:
    query = parse_search_query({"hospital": f"{HOSPITAL_ID}x", "specialty": "1234"})

    assert (query.hospital_id, query.specialty_id) == (None, None)


def returns_the_date_when_from_is_a_calendar_date() -> None:
    assert parse_search_query({"from": "2030-02-28"}).earliest_date == date(2030, 2, 28)


def returns_no_date_when_date_is_2030_13_40() -> None:
    assert parse_search_query({"from": "2030-13-40"}).earliest_date is None


def returns_window_and_time_of_day_when_values_are_known() -> None:
    cases = [
        parse_search_query({"window": window, "time_of_day": period})
        for window, period in (("today", "morning"), ("3_days", "afternoon"), ("7_days", "evening"))
    ]

    assert [(case.window, case.time_of_day) for case in cases] == [
        ("today", "morning"),
        ("3_days", "afternoon"),
        ("7_days", "evening"),
    ]


def returns_sort_when_sort_is_a_name_order() -> None:
    sorts = [parse_search_query({"sort": value}).sort for value in ("name_asc", "name_desc")]

    assert sorts == ["name_asc", "name_desc"]


def returns_truncates_text_at_100_characters() -> None:
    assert parse_search_query({"q": "a" * 150}).text == "a" * 100


def returns_trimmed_text_and_city_when_they_have_spaces_around() -> None:
    query = parse_search_query({"q": "  heart  ", "city": " Berlin "})

    assert (query.text, query.city) == ("heart", "Berlin")


def returns_no_city_when_city_is_blank() -> None:
    assert parse_search_query({"city": "   "}).city is None


def returns_ignores_unknown_keys() -> None:
    assert parse_search_query({"surprise": "1"}) == parse_search_query({})


def returns_the_specialty_and_type_ids_when_uuids_are_well_formed() -> None:
    specialty_id, type_id = uuid4(), uuid4()

    query = parse_search_query({"specialty": str(specialty_id), "appointment_type": str(type_id)})

    assert (query.specialty_id, query.appointment_type_id) == (specialty_id, type_id)


def returns_no_type_filter_when_type_id_is_malformed() -> None:
    assert parse_search_query({"appointment_type": "1234"}).appointment_type_id is None
