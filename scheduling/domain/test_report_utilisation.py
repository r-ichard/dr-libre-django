"""Task 21, #2: minutes of active appointments over the minutes clinicians could work."""

from datetime import UTC, date, datetime, time, timedelta

BERLIN = "Europe/Berlin"


def _days(first: date, count: int) -> list[date]:
    return [first + timedelta(days=offset) for offset in range(count)]


def _rule(
    weekday: int,
    start: time = time(8, 0),
    end: time = time(16, 0),
    valid_from: date = date(2026, 1, 1),
    valid_to: date | None = None,
    clinician_id: str = "c1",
    time_zone: str = "UTC",
):  # noqa: ANN202 - a test helper, the type is the dataclass under test
    from scheduling.domain.report_utilisation import RuleHours

    return RuleHours(
        clinician_id=clinician_id,
        weekday=weekday,
        start_time=start,
        end_time=end,
        valid_from=valid_from,
        valid_to=valid_to,
        time_zone=time_zone,
    )


def _off(starts_at: datetime, ends_at: datetime, clinician_id: str = "c1"):  # noqa: ANN202
    from scheduling.domain.report_utilisation import OffPeriod

    return OffPeriod(clinician_id=clinician_id, starts_at=starts_at, ends_at=ends_at)


def _visit(starts_at: datetime, minutes: int, status: str = "BOOKED"):  # noqa: ANN202
    from scheduling.domain.report_figures import ReportedVisit
    from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus

    return ReportedVisit(
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=minutes),
        status=AppointmentStatus(status),
        source=AppointmentSource.STAFF,
        time_zone="UTC",
        clinician_id="c1",
    )


# 2026-03-10 is a Tuesday: weekday 2, Sunday being 0.
TUESDAY = date(2026, 3, 10)
TUESDAY_RULE_DAY = 8 * 60


def returns_available_minutes_of_rule_hours_in_range() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    assert available_minutes([_rule(2)], [], [TUESDAY]) == TUESDAY_RULE_DAY


def returns_zero_available_minutes_when_no_rule_matches_the_weekday() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    assert available_minutes([_rule(3)], [], [TUESDAY]) == 0


def returns_utilisation_minutes_over_available_minutes() -> None:
    from scheduling.domain.report_utilisation import utilisation

    visits = [_visit(datetime(2026, 3, 10, 8, 0, tzinfo=UTC), 240)]

    assert utilisation(visits, [_rule(2)], [], [TUESDAY]) == "50 %"


def returns_counts_only_active_appointments_in_utilisation() -> None:
    from scheduling.domain.report_utilisation import utilisation

    visits = [
        _visit(datetime(2026, 3, 10, 8, 0, tzinfo=UTC), 120),
        _visit(datetime(2026, 3, 10, 10, 0, tzinfo=UTC), 120, "CANCELLED"),
        _visit(datetime(2026, 3, 10, 12, 0, tzinfo=UTC), 120, "NO_SHOW"),
    ]

    assert utilisation(visits, [_rule(2)], [], [TUESDAY]) == "25 %"


def returns_na_when_available_minutes_are_zero() -> None:
    from scheduling.domain.report_utilisation import utilisation

    visits = [_visit(datetime(2026, 3, 10, 8, 0, tzinfo=UTC), 60)]

    assert utilisation(visits, [], [], [TUESDAY]) == "n/a"


def returns_one_hour_less_for_a_rule_day_across_spring_forward() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    # Berlin skips 02:00 to 03:00 on 2026-03-29: wall clock 00:00 to 23:00 is 22 real hours.
    rule = _rule(0, time(0, 0), time(23, 0), time_zone=BERLIN)

    assert available_minutes([rule], [], [date(2026, 3, 29)]) == 22 * 60


def returns_rule_minutes_in_real_time_when_rule_spans_the_clock_change() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rule = _rule(0, time(1, 0), time(5, 0), time_zone=BERLIN)

    assert available_minutes([rule], [], [date(2026, 3, 29)]) == 3 * 60


def returns_five_hours_when_rule_spans_the_clock_going_back() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rule = _rule(0, time(1, 0), time(5, 0), time_zone=BERLIN)

    assert available_minutes([rule], [], [date(2026, 10, 25)]) == 5 * 60


def returns_rule_minutes_only_from_valid_from_in_range() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rule = _rule(2, valid_from=date(2026, 3, 17))
    days = [date(2026, 3, 10), date(2026, 3, 17)]

    assert available_minutes([rule], [], days) == TUESDAY_RULE_DAY


def returns_rule_minutes_only_until_valid_to_in_range() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rule = _rule(2, valid_to=date(2026, 3, 10))
    days = [date(2026, 3, 10), date(2026, 3, 17)]

    assert available_minutes([rule], [], days) == TUESDAY_RULE_DAY


def returns_available_minutes_less_time_off_covering_part_of_a_day() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    off = _off(datetime(2026, 3, 10, 10, 0, tzinfo=UTC), datetime(2026, 3, 10, 12, 30, tzinfo=UTC))

    assert available_minutes([_rule(2)], [off], [TUESDAY]) == TUESDAY_RULE_DAY - 150


def returns_counts_overlapping_time_off_once() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    first = _off(datetime(2026, 3, 10, 10, 0, tzinfo=UTC), datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    second = _off(
        datetime(2026, 3, 10, 11, 0, tzinfo=UTC), datetime(2026, 3, 10, 13, 0, tzinfo=UTC)
    )

    assert available_minutes([_rule(2)], [first, second], [TUESDAY]) == TUESDAY_RULE_DAY - 180


def returns_subtracts_nothing_when_time_off_is_outside_the_rule_hours() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    off = _off(datetime(2026, 3, 10, 17, 0, tzinfo=UTC), datetime(2026, 3, 11, 7, 0, tzinfo=UTC))

    assert available_minutes([_rule(2)], [off], [TUESDAY]) == TUESDAY_RULE_DAY


def returns_subtracts_only_the_time_off_of_the_same_clinician() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    other = _off(
        datetime(2026, 3, 10, 8, 0, tzinfo=UTC), datetime(2026, 3, 10, 16, 0, tzinfo=UTC), "c2"
    )

    assert available_minutes([_rule(2)], [other], [TUESDAY]) == TUESDAY_RULE_DAY


def returns_adds_the_rule_hours_of_every_clinician() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rules = [_rule(2), _rule(2, clinician_id="c2", start=time(9, 0), end=time(12, 0))]

    assert available_minutes(rules, [], [TUESDAY]) == TUESDAY_RULE_DAY + 180


def returns_n_a_only_for_zero_available_minutes_not_for_one() -> None:
    from scheduling.domain.report_utilisation import utilisation

    visits = [_visit(datetime(2026, 3, 10, 8, 0, tzinfo=UTC), 1)]
    rules = [_rule(2, start=time(8, 0), end=time(8, 1))]

    assert utilisation(visits, rules, [], [TUESDAY]) == "100 %"


def returns_whole_minutes_rounded_down_when_rule_hours_have_seconds() -> None:
    from scheduling.domain.report_utilisation import available_minutes

    rules = [_rule(2, start=time(8, 0, 0), end=time(8, 0, 59))]

    assert available_minutes(rules, [], [TUESDAY]) == 0
