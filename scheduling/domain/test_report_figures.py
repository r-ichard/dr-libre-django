"""Task 21, #1: the figures of section 13, each as the table defines it."""

from datetime import UTC, date, datetime

from scheduling.domain.report_figures import ReportedVisit
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus

NOON = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 10, 12, 30, tzinfo=UTC)


def _visit(
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    source: AppointmentSource = AppointmentSource.STAFF,
    starts_at: datetime = NOON,
    time_zone: str = "UTC",
    clinician_id: str = "c1",
) -> ReportedVisit:
    return ReportedVisit(
        starts_at=starts_at,
        ends_at=LATER,
        status=status,
        source=source,
        time_zone=time_zone,
        clinician_id=clinician_id,
    )


def returns_appointments_not_cancelled_count() -> None:
    from scheduling.domain.report_figures import appointment_count

    visits = [
        _visit(),
        _visit(AppointmentStatus.NO_SHOW),
        _visit(AppointmentStatus.COMPLETED),
        _visit(AppointmentStatus.CANCELLED),
    ]

    assert appointment_count(visits) == 3


def returns_cancellations_count() -> None:
    from scheduling.domain.report_figures import cancellation_count

    visits = [_visit(), _visit(AppointmentStatus.CANCELLED), _visit(AppointmentStatus.CANCELLED)]

    assert cancellation_count(visits) == 2


def returns_no_show_rate_over_non_cancelled() -> None:
    from scheduling.domain.report_figures import no_show_rate

    visits = [
        _visit(AppointmentStatus.NO_SHOW),
        _visit(),
        _visit(),
        _visit(),
        _visit(AppointmentStatus.CANCELLED),
    ]

    assert no_show_rate(visits) == "25 %"


def returns_na_when_no_appointment_is_not_cancelled_for_no_show_rate() -> None:
    from scheduling.domain.report_figures import no_show_rate

    assert no_show_rate([_visit(AppointmentStatus.CANCELLED)]) == "n/a"
    assert no_show_rate([]) == "n/a"


def returns_online_share_counting_online_and_round_robin_only() -> None:
    from scheduling.domain.report_figures import online_share

    visits = [
        _visit(source=AppointmentSource.ONLINE),
        _visit(source=AppointmentSource.ROUND_ROBIN),
        _visit(source=AppointmentSource.ONLINE),
        _visit(source=AppointmentSource.STAFF),
        _visit(AppointmentStatus.CANCELLED, AppointmentSource.ONLINE),
    ]

    assert online_share(visits) == "75 %"


def returns_na_when_no_appointment_is_not_cancelled_for_online_share() -> None:
    from scheduling.domain.report_figures import online_share

    assert online_share([_visit(AppointmentStatus.CANCELLED, AppointmentSource.ONLINE)]) == "n/a"


def returns_waitlist_size_of_waiting_and_offered_regardless_of_range() -> None:
    from scheduling.domain.report_figures import waitlist_size
    from scheduling.domain.vocabulary import WaitlistStatus

    statuses = [
        WaitlistStatus.WAITING,
        WaitlistStatus.OFFERED,
        WaitlistStatus.OFFERED,
        WaitlistStatus.BOOKED,
        WaitlistStatus.EXPIRED,
    ]

    assert waitlist_size(statuses) == 3


def returns_zero_waitlist_size_when_nobody_waits() -> None:
    from scheduling.domain.report_figures import waitlist_size

    assert waitlist_size([]) == 0


def returns_whole_percent_rounded_half_up_when_denominator_is_not_zero() -> None:
    from scheduling.domain.report_figures import percent_text

    assert percent_text(1, 3) == "33 %"
    assert percent_text(2, 3) == "67 %"
    assert percent_text(1, 8) == "13 %"
    assert percent_text(0, 5) == "0 %"
    assert percent_text(5, 5) == "100 %"


def returns_na_when_denominator_is_zero() -> None:
    from scheduling.domain.report_figures import percent_text

    assert percent_text(0, 0) == "n/a"


def returns_counts_appointment_on_hospital_day_once() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    sydney_visit = _visit(
        starts_at=datetime(2026, 3, 10, 23, 30, tzinfo=UTC), time_zone="Australia/Sydney"
    )
    days = [date(2026, 3, 10), date(2026, 3, 11)]

    counts = appointments_per_day([sydney_visit], days)

    assert [(entry.day, entry.count) for entry in counts] == [
        (date(2026, 3, 10), 0),
        (date(2026, 3, 11), 1),
    ]


def returns_counts_same_instant_on_the_earlier_day_when_hospital_is_behind_utc() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    new_york_visit = _visit(
        starts_at=datetime(2026, 3, 11, 2, 0, tzinfo=UTC), time_zone="America/New_York"
    )
    days = [date(2026, 3, 10), date(2026, 3, 11)]

    counts = appointments_per_day([new_york_visit], days)

    assert [entry.count for entry in counts] == [1, 0]


def returns_leaves_cancelled_and_out_of_range_appointments_out_of_the_day_counts() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    visits = [
        _visit(AppointmentStatus.CANCELLED),
        _visit(starts_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC)),
        _visit(),
    ]

    counts = appointments_per_day(visits, [date(2026, 3, 10)])

    assert [entry.count for entry in counts] == [1]


def returns_bar_widths_scaled_to_the_busiest_day() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    visits = [
        _visit(),
        _visit(),
        _visit(),
        _visit(starts_at=datetime(2026, 3, 11, 12, 0, tzinfo=UTC)),
    ]
    days = [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)]

    counts = appointments_per_day(visits, days)

    assert [entry.bar_width for entry in counts] == [100, 33, 0]


def returns_zero_bar_widths_when_no_day_has_an_appointment() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    counts = appointments_per_day([], [date(2026, 3, 10)])

    assert [(entry.count, entry.bar_width) for entry in counts] == [(0, 0)]


def returns_no_day_counts_when_there_are_no_days() -> None:
    from scheduling.domain.report_figures import appointments_per_day

    assert appointments_per_day([], []) == []


def returns_top_five_busiest_by_count_then_id() -> None:
    from scheduling.domain.report_figures import busiest_clinicians

    visits = (
        [_visit(clinician_id="g")] * 1
        + [_visit(clinician_id="b")] * 3
        + [_visit(clinician_id="a")] * 3
        + [_visit(clinician_id="c")] * 5
        + [_visit(clinician_id="d")] * 2
        + [_visit(clinician_id="e")] * 2
        + [_visit(clinician_id="f")] * 2
        + [_visit(AppointmentStatus.CANCELLED, clinician_id="h")] * 9
    )

    busiest = busiest_clinicians(visits)

    assert [(entry.clinician_id, entry.count) for entry in busiest] == [
        ("c", 5),
        ("a", 3),
        ("b", 3),
        ("d", 2),
        ("e", 2),
    ]
