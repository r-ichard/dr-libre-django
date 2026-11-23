"""Section 13: the dates of a report range and what today is."""

from datetime import UTC, date, datetime

import pytest


def returns_seven_days_ending_today_when_range_is_missing() -> None:
    from scheduling.domain.report_range import report_days

    days = report_days("", date(2026, 3, 10))

    assert days[0] == date(2026, 3, 4)
    assert days[-1] == date(2026, 3, 10)
    assert len(days) == 7


def returns_only_today_when_range_is_today() -> None:
    from scheduling.domain.report_range import report_days

    assert report_days("today", date(2026, 3, 10)) == [date(2026, 3, 10)]


def returns_thirty_days_ending_today_when_range_is_thirty() -> None:
    from scheduling.domain.report_range import report_days

    days = report_days("30", date(2026, 3, 10))

    assert days[0] == date(2026, 2, 9)
    assert days[-1] == date(2026, 3, 10)
    assert len(days) == 30


@pytest.mark.parametrize("unusable", ["", "90", "7;", "٧", "-7", "0", "7 ", "TODAY", "=cmd"])
def returns_seven_days_when_range_is_unusable(unusable: str) -> None:
    from scheduling.domain.report_range import report_days

    assert len(report_days(unusable, date(2026, 3, 10))) == 7


def returns_latest_date_among_hospital_zones_as_today() -> None:
    from scheduling.domain.report_range import current_report_date

    now = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)

    assert current_report_date(now, ["America/New_York", "Australia/Sydney"]) == date(2026, 3, 11)


def returns_utc_date_as_today_when_there_is_no_hospital() -> None:
    from scheduling.domain.report_range import current_report_date

    assert current_report_date(datetime(2026, 3, 10, 23, 30, tzinfo=UTC), []) == date(2026, 3, 10)
