"""Section 6.1 to 6.5: public search on the database, same slots as booking would accept."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
from django.db import connection
from django.db.models import Model
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Success
from scheduling.domain.free_slots import TimeRange
from scheduling.domain.request_context import RequestContext
from scheduling.domain.search_query import parse_search_query
from scheduling.models import ClinicianProfile, Department
from scheduling.models.builders import add_clinician, make
from scheduling.use_cases.free_slots_query import find_free_slots
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.search import search_public
from scheduling.use_cases.search_types import ProviderResult

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LEAD_END = NOW + timedelta(minutes=120)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
MONDAY_FIRST = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-search", NOW)):
        yield


def _clinician(
    name: str,
    department: Model,
    rule_fields: dict[str, object] | None = None,
    **profile: object,
) -> ClinicianProfile:
    user = make("User", role="CLINICIAN", full_name=name)
    return add_clinician(department, rule_fields or HOUR_OF_SLOTS, user=user, **profile)


def _names(kind: str, **raw: str) -> list[str]:
    page = search_public(kind, parse_search_query(raw), NOW)
    return [
        result.full_name if isinstance(result, ProviderResult) else result.name
        for result in page.results
    ]


def _department(**hospital: object) -> Department:
    department = make("Department", hospital=make("Hospital", **hospital))
    assert isinstance(department, Department)
    return department


def returns_only_active_bookable_data_when_inactive_rows_exist() -> None:
    visible = _department(name="Visible Hospital")
    make("AppointmentType", department=visible)
    _clinician("Visible Vera", visible)
    inactive_hospital = _department(is_active=False)
    make("AppointmentType", department=inactive_hospital)
    _clinician("Hidden Hospital Hal", inactive_hospital)
    inactive_specialty = make("Department", hospital=visible.hospital)
    make("AppointmentType", department=inactive_specialty)
    _clinician(
        "Hidden Specialty Sam", inactive_specialty, specialty=make("Specialty", is_active=False)
    )
    left = make("Department", hospital=visible.hospital)
    make("AppointmentType", department=left)
    gone = _clinician("Hidden User Uma", left)
    gone.user.refresh_from_db()
    gone.user.is_active = False
    gone.user.save()

    assert _names("providers") == ["Visible Vera"]


def returns_omits_clinician_when_department_has_no_online_bookable_type() -> None:
    offline = make("Department")
    make("AppointmentType", department=offline, is_bookable_online=False)
    _clinician("Offline Olga", offline)
    retired = make("Department")
    make("AppointmentType", department=retired, is_active=False)
    _clinician("Retired Rita", retired)

    assert _names("providers") == []


def returns_omits_hospital_and_specialty_when_no_listed_provider_belongs_to_them() -> None:
    offline = make("Department")
    make("AppointmentType", department=offline, is_bookable_online=False)
    _clinician("Offline Olga", offline)

    assert (_names("hospitals"), _names("specialties")) == ([], [])


def returns_lists_slots_equal_to_find_free_slots_when_same_type_and_range() -> None:
    department = make("Department")
    appointment_type = make("AppointmentType", department=department)
    clinician = _clinician("Vera Slots", department)
    window = TimeRange(LEAD_END, LEAD_END + timedelta(days=31))

    found = find_free_slots(appointment_type.pk, clinician.pk, window)

    assert isinstance(found, Success)
    expected = [offer.start for offer in found.value.offers][:3]
    listed = search_public("providers", parse_search_query({}), NOW).results[0].next_starts
    assert listed == expected
    assert expected[0] == MONDAY_FIRST


def returns_omits_slot_when_booking_hold_covers_it() -> None:
    department = make("Department")
    appointment_type = make("AppointmentType", department=department)
    clinician = _clinician("Vera Held", department)
    make(
        "BookingHold",
        clinician=clinician,
        appointment_type=appointment_type,
        starts_at=MONDAY_FIRST,
        ends_at=MONDAY_FIRST + timedelta(minutes=30),
    )

    listed = search_public("providers", parse_search_query({}), NOW).results[0].next_starts

    assert MONDAY_FIRST not in listed
    assert listed[0] == MONDAY_FIRST + timedelta(minutes=30)


def returns_omits_slot_when_appointment_or_time_off_covers_it() -> None:
    department = make("Department")
    appointment_type = make("AppointmentType", department=department)
    clinician = _clinician("Vera Busy", department)
    make(
        "Appointment",
        clinician=clinician,
        appointment_type=appointment_type,
        starts_at=MONDAY_FIRST,
        ends_at=MONDAY_FIRST + timedelta(minutes=30),
    )
    make(
        "TimeOff",
        clinician=clinician,
        starts_at=MONDAY_FIRST + timedelta(minutes=30),
        ends_at=MONDAY_FIRST + timedelta(hours=1),
    )

    listed = search_public("providers", parse_search_query({}), NOW).results[0].next_starts

    assert listed[0] == MONDAY_FIRST + timedelta(days=7)


def returns_names_shortest_type_when_no_type_filtered() -> None:
    department = make("Department")
    make("AppointmentType", department=department, name="Long visit", duration_minutes=60)
    make("AppointmentType", department=department, name="Short visit", duration_minutes=20)
    _clinician("Vera Types", department)

    result = search_public("providers", parse_search_query({}), NOW).results[0]

    assert result.appointment_type_name == "Short visit"


def returns_uses_filtered_type_for_slots() -> None:
    department = make("Department")
    long_type = make(
        "AppointmentType", department=department, name="Long visit", duration_minutes=60
    )
    make("AppointmentType", department=department, name="Short visit", duration_minutes=20)
    _clinician("Vera Types", department)

    query = parse_search_query({"appointment_type": str(long_type.pk)})
    result = search_public("providers", query, NOW).results[0]

    assert (result.appointment_type_name, len(result.next_starts)) == ("Long visit", 3)
    assert result.next_starts[0] == MONDAY_FIRST


def returns_nothing_when_filtered_type_belongs_to_another_department() -> None:
    mine = make("Department")
    make("AppointmentType", department=mine)
    _clinician("Vera Mine", mine)
    other_type = make("AppointmentType", department=make("Department"))

    assert _names("providers", appointment_type=str(other_type.pk)) == []


def returns_nothing_when_filter_names_an_id_that_does_not_exist() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Vera Mine", department)

    missing = "00000000-0000-4000-8000-000000000000"

    assert _names("providers", hospital=missing) == []


def returns_lists_result_after_those_with_slots_when_nothing_free_in_90_days() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Aaron Idle", department, {"valid_from": datetime(2031, 1, 1).date()})
    _clinician("Zed Busy", department)

    results = search_public("providers", parse_search_query({}), NOW).results

    assert [(result.full_name, result.has_availability) for result in results] == [
        ("Zed Busy", True),
        ("Aaron Idle", False),
    ]


def returns_keeps_clinician_without_slots_listed_when_no_availability_filter_is_set() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Aaron Idle", department, {"valid_from": datetime(2031, 1, 1).date()})

    assert _names("providers") == ["Aaron Idle"]


def returns_drops_clinician_without_slots_when_an_availability_filter_is_set() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Aaron Idle", department, {"valid_from": datetime(2031, 1, 1).date()})

    assert _names("providers", window="7_days") == []


def returns_time_filter_drops_morning_only_clinician_and_trims_evening_slots() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Mona Morning", department, HOUR_OF_SLOTS)
    evening = {"start_time": time(17, 0), "end_time": time(19, 0), "slot_step_minutes": 30}
    _clinician("Eve Evening", department, evening)

    page = search_public("providers", parse_search_query({"time_of_day": "evening"}), NOW)

    assert [result.full_name for result in page.results] == ["Eve Evening"]
    assert page.results[0].next_starts == [
        datetime(2030, 1, 7, 16, 30, tzinfo=UTC),
        datetime(2030, 1, 7, 17, 0, tzinfo=UTC),
        datetime(2030, 1, 7, 17, 30, tzinfo=UTC),
    ]


def returns_filters_combine_with_and_when_specialty_and_city_are_both_given() -> None:
    berlin = _department(city="Berlin")
    make("AppointmentType", department=berlin)
    heart = make("Specialty", name="Cardiology")
    _clinician("Both Bea", berlin, specialty=heart)
    _clinician("Wrong Specialty Walt", berlin)
    elsewhere = _department(city="Hamburg")
    make("AppointmentType", department=elsewhere)
    _clinician("Wrong City Cy", elsewhere, specialty=heart)

    names = _names("providers", specialty=str(heart.pk), city="berlin")

    assert names == ["Both Bea"]


def returns_matches_text_on_hospital_name_without_case() -> None:
    department = _department(name="Riverside General")
    make("AppointmentType", department=department)
    _clinician("Vera Text", department)

    assert _names("providers", q="RIVERSIDE gen") == ["Vera Text"]


def returns_hospital_result_counts_bookable_providers_and_those_with_a_slot() -> None:
    department = _department(name="Counting Hospital")
    make("AppointmentType", department=department)
    _clinician("Free Fay", department)
    _clinician("Idle Ian", department, {"valid_from": datetime(2031, 1, 1).date()})

    result = search_public("hospitals", parse_search_query({}), NOW).results[0]

    assert (result.bookable_provider_count, result.providers_with_availability_count) == (2, 1)
    assert result.earliest_start == MONDAY_FIRST


def returns_specialty_result_counts_providers_and_hospitals_and_picks_the_earliest_slot() -> None:
    heart = make("Specialty", name="Cardiology")
    for hospital_name, hour in (("First Hospital", 12), ("Second Hospital", 10)):
        department = _department(name=hospital_name)
        make("AppointmentType", department=department)
        rule = {"start_time": time(hour, 0), "end_time": time(hour + 1, 0), "slot_step_minutes": 30}
        _clinician(f"Doc {hospital_name}", department, rule, specialty=heart)
        _clinician(f"Second {hospital_name}", department, rule, specialty=heart)

    result = search_public("specialties", parse_search_query({}), NOW).results[0]

    assert (result.provider_count, result.hospital_count) == (4, 2)
    assert result.earliest_start == datetime(2030, 1, 7, 9, 0, tzinfo=UTC)


def returns_page_total_and_count_when_results_exceed_page_size() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    for number in range(12):
        _clinician(f"Doc {number:02d}", department)

    page = search_public(
        "providers", parse_search_query({"page_size": "10", "page": "9", "sort": "name_asc"}), NOW
    )

    assert (page.total, page.page, page.page_count, len(page.results)) == (12, 2, 2, 2)
    assert [result.full_name for result in page.results] == ["Doc 10", "Doc 11"]


def returns_sorts_the_whole_set_before_cutting_the_page() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    for number in range(12):
        _clinician(f"Doc {number:02d}", department)

    page = search_public(
        "providers", parse_search_query({"page_size": "10", "sort": "name_desc"}), NOW
    )

    assert page.results[0].full_name == "Doc 11"


def _build_clinicians(count: int) -> None:
    for number in range(count):
        department = _department(name=f"Hospital {number}")
        appointment_type = make("AppointmentType", department=department, buffer_minutes=5)
        clinician = _clinician(f"Doc {number}", department, specialty=make("Specialty"))
        make(
            "BookingHold",
            clinician=clinician,
            appointment_type=appointment_type,
            starts_at=MONDAY_FIRST,
            ends_at=MONDAY_FIRST + timedelta(minutes=30),
        )
        make(
            "Appointment",
            clinician=clinician,
            appointment_type=appointment_type,
            starts_at=MONDAY_FIRST + timedelta(minutes=30),
            ends_at=MONDAY_FIRST + timedelta(minutes=60),
        )


@pytest.mark.parametrize("kind", ["providers", "hospitals", "specialties"])
def returns_runs_same_number_of_queries_when_2_or_12_clinicians_match(kind: str) -> None:
    query = parse_search_query({"page_size": "50"})
    _build_clinicians(2)
    with CaptureQueriesContext(connection) as few:
        search_public(kind, query, NOW)
    _build_clinicians(10)

    with CaptureQueriesContext(connection) as many:
        page = search_public(kind, query, NOW)

    assert page.total == 12
    assert len(many) == len(few)
    assert len(many) <= 8


def returns_a_slot_in_the_last_days_of_the_horizon_when_nothing_is_free_before() -> None:
    department = make("Department")
    make("AppointmentType", department=department)
    _clinician("Late Lena", department, {"valid_from": datetime(2030, 4, 1).date()})

    result = search_public("providers", parse_search_query({}), NOW).results[0]

    assert (result.has_availability, result.next_starts[0].date().isoformat()) == (
        True,
        "2030-04-01",
    )


def returns_omits_a_far_booked_slot_when_the_appointment_is_beyond_the_first_month() -> None:
    department = make("Department")
    appointment_type = make("AppointmentType", department=department)
    clinician = _clinician("Far Fred", department, {"valid_from": datetime(2030, 4, 1).date()})
    first_far = search_public("providers", parse_search_query({}), NOW).results[0].next_starts[0]
    make(
        "Appointment",
        clinician=clinician,
        appointment_type=appointment_type,
        starts_at=first_far,
        ends_at=first_far + timedelta(minutes=30),
    )

    listed = search_public("providers", parse_search_query({}), NOW).results[0].next_starts

    assert first_far not in listed
    assert listed[0] == first_far + timedelta(minutes=30)
