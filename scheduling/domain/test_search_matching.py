"""Section 6.1, 6.2 and 6.3: text match, search range and time of day, in the hospital's zone."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import TimeRange
from scheduling.domain.search_matching import (
    ProviderRecord,
    matches_text,
    search_range,
    time_of_day_of,
)

BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LEAD = timedelta(minutes=120)
HORIZON = timedelta(days=90)

PROVIDER = ProviderRecord(
    id=uuid4(),
    full_name="Ada Lovelace",
    title="Dr",
    hospital_name="Riverside General",
    city="Potsdam",
    time_zone="Europe/Berlin",
    specialty_name="Cardiology",
    department_name="Heart Centre",
    type_names=("Quick Check", "Long Consultation"),
)


def returns_true_when_text_is_empty() -> None:
    assert matches_text("", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_hospital_name() -> None:
    assert matches_text("SIDE GEN", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_city() -> None:
    assert matches_text("POTSD", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_clinician_name() -> None:
    assert matches_text("LOVEL", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_specialty_name() -> None:
    assert matches_text("DIOLO", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_department_name() -> None:
    assert matches_text("ART CEN", PROVIDER)


def returns_true_when_text_is_partial_and_upper_case_for_appointment_type_name() -> None:
    assert matches_text("CONSULT", PROVIDER)


def returns_false_when_no_field_contains_text() -> None:
    assert not matches_text("zebra", PROVIDER)


def returns_false_when_text_only_matches_the_title() -> None:
    assert not matches_text(
        "dr",
        replace(
            PROVIDER,
            full_name="Ada",
            title="Dr",
            city="Bonn",
            hospital_name="X",
            specialty_name="Y",
            department_name="Z",
            type_names=("W",),
        ),
    )


def returns_false_when_only_part_of_a_multi_word_text_is_found() -> None:
    assert not matches_text("ada zebra", PROVIDER)


def returns_the_lead_time_to_ninety_days_when_nothing_narrows_the_range() -> None:
    result = search_range(NOW, BERLIN, "any", None)

    assert result == TimeRange(NOW + LEAD, NOW + HORIZON)


def returns_local_midnight_as_end_when_window_is_today() -> None:
    result = search_range(NOW, BERLIN, "today", None)

    assert result == TimeRange(NOW + LEAD, datetime(2030, 1, 7, 23, 0, tzinfo=UTC))


def returns_now_plus_three_days_as_end_when_window_is_3_days() -> None:
    result = search_range(NOW, BERLIN, "3_days", None)

    assert result == TimeRange(NOW + LEAD, NOW + timedelta(days=3))


def returns_now_plus_seven_days_as_end_when_window_is_7_days() -> None:
    result = search_range(NOW, BERLIN, "7_days", None)

    assert result == TimeRange(NOW + LEAD, NOW + timedelta(days=7))


def returns_local_midnight_of_the_date_as_start_when_date_is_later_than_the_lead() -> None:
    result = search_range(NOW, BERLIN, "any", datetime(2030, 1, 9, tzinfo=UTC).date())

    assert result == TimeRange(datetime(2030, 1, 8, 23, 0, tzinfo=UTC), NOW + HORIZON)


def returns_the_lead_as_start_when_date_is_today() -> None:
    result = search_range(NOW, BERLIN, "any", datetime(2030, 1, 7, tzinfo=UTC).date())

    assert result == TimeRange(NOW + LEAD, NOW + HORIZON)


def returns_nothing_when_date_is_after_the_horizon() -> None:
    assert search_range(NOW, BERLIN, "any", datetime(2030, 6, 1, tzinfo=UTC).date()) is None


def returns_nothing_when_window_is_today_and_date_is_tomorrow() -> None:
    assert search_range(NOW, BERLIN, "today", datetime(2030, 1, 8, tzinfo=UTC).date()) is None


def returns_nothing_when_the_lead_passes_local_midnight_and_window_is_today() -> None:
    late = datetime(2030, 1, 7, 21, 30, tzinfo=UTC)

    assert search_range(late, BERLIN, "today", None) is None


def returns_morning_when_local_time_is_11_59() -> None:
    assert time_of_day_of(datetime(2030, 1, 7, 10, 59, tzinfo=UTC), BERLIN) == "morning"


def returns_afternoon_when_local_time_is_12_00() -> None:
    assert time_of_day_of(datetime(2030, 1, 7, 11, 0, tzinfo=UTC), BERLIN) == "afternoon"


def returns_afternoon_when_local_time_is_17_00() -> None:
    assert time_of_day_of(datetime(2030, 1, 7, 16, 0, tzinfo=UTC), BERLIN) == "afternoon"


def returns_evening_when_local_time_is_17_01() -> None:
    assert time_of_day_of(datetime(2030, 1, 7, 16, 1, tzinfo=UTC), BERLIN) == "evening"


def returns_morning_when_local_time_is_midnight() -> None:
    assert time_of_day_of(datetime(2030, 1, 6, 23, 0, tzinfo=UTC), BERLIN) == "morning"


def returns_afternoon_when_utc_says_morning_but_summer_time_says_noon() -> None:
    summer = datetime(2030, 7, 1, 10, 0, tzinfo=UTC)

    assert time_of_day_of(summer, BERLIN) == "afternoon"


def returns_morning_when_the_same_utc_hour_is_before_noon_in_winter() -> None:
    winter = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)

    assert time_of_day_of(winter, BERLIN) == "morning"


def returns_the_local_day_end_when_window_is_today_and_utc_date_is_one_day_behind() -> None:
    auckland = ZoneInfo("Pacific/Auckland")
    evening_utc = datetime(2030, 1, 7, 20, 0, tzinfo=UTC)

    result = search_range(evening_utc, auckland, "today", None)

    assert result == TimeRange(evening_utc + LEAD, datetime(2030, 1, 8, 11, 0, tzinfo=UTC))
