"""Section 6.5: every search state lives in the address, built from the parsed query."""

from dataclasses import replace
from datetime import date
from uuid import uuid4

from scheduling.domain.search_query import Location, parse_search_query

DEFAULT_QUERY = parse_search_query({})
SPECIALTY_ID = uuid4()


def returns_default_free_address_when_query_is_all_defaults() -> None:
    from scheduling.domain.search_address import search_href

    href = search_href(DEFAULT_QUERY, "providers")

    assert href == "/"


def returns_only_changed_keys_when_query_has_text_and_filters() -> None:
    from scheduling.domain.search_address import search_href

    query = replace(DEFAULT_QUERY, text="heart", specialty_id=SPECIALTY_ID, sort="name_asc")

    href = search_href(query, "hospitals")

    assert href == f"/?q=heart&list=hospitals&specialty={SPECIALTY_ID}&sort=name_asc"


def returns_page_one_when_a_filter_changes() -> None:
    from scheduling.domain.search_address import search_href

    query = replace(DEFAULT_QUERY, page=4)

    href = search_href(query, "providers", text="knee")

    assert href == "/?q=knee"


def returns_page_when_only_page_changes() -> None:
    from scheduling.domain.search_address import search_href

    href = search_href(DEFAULT_QUERY, "providers", page=3)

    assert href == "/?page=3"


def returns_every_other_parameter_when_page_size_changes() -> None:
    from scheduling.domain.search_address import search_href

    location = Location(latitude=52.5, longitude=13.4)
    query = replace(
        DEFAULT_QUERY, text="heart", city="Berlin", sort="distance", location=location, page=2
    )

    href = search_href(query, "specialties", page_size=50)

    assert href == (
        "/?q=heart&list=specialties&city=Berlin&sort=distance"
        "&page_size=50&latitude=52.5&longitude=13.4"
    )


def returns_providers_when_list_is_unknown() -> None:
    from scheduling.domain.search_address import parse_list_kind

    kind = parse_list_kind("pharmacies")

    assert kind == "providers"


def returns_the_kind_when_list_is_known() -> None:
    from scheduling.domain.search_address import parse_list_kind

    kind = parse_list_kind("specialties")

    assert kind == "specialties"


def returns_percent_encoded_text_when_text_has_ampersand_and_space() -> None:
    from scheduling.domain.search_address import search_href

    query = replace(DEFAULT_QUERY, text="a&b c")

    href = search_href(query, "providers")

    assert href == "/?q=a%26b+c"


def returns_every_remaining_filter_key_when_all_filters_are_set() -> None:
    from scheduling.domain.search_address import search_href

    hospital_id, type_id = uuid4(), uuid4()
    query = replace(
        DEFAULT_QUERY,
        hospital_id=hospital_id,
        appointment_type_id=type_id,
        earliest_date=date(2030, 12, 3),
        time_of_day="morning",
        window="7_days",
    )

    href = search_href(query, "providers")

    assert href == (
        f"/?hospital={hospital_id}&appointment_type={type_id}"
        "&from=2030-12-03&window=7_days&time_of_day=morning"
    )


def returns_explicit_page_size_when_it_is_changed_to_the_default() -> None:
    from scheduling.domain.search_address import search_href

    query = replace(DEFAULT_QUERY, page_size=50)

    href = search_href(query, "providers", page_size=20)

    assert href == "/?page_size=20"
