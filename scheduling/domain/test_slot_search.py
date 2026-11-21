"""Section 5.1: no clinician named, the union of free slots with who is free at each start."""

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import (
    AvailabilityWindow,
    BusyInterval,
    ExistingAppointment,
    SlotType,
    TimeRange,
)
from scheduling.domain.slot_search import (
    MAXIMUM_QUERY_DAYS,
    ClinicianSchedule,
    QueryTooWide,
    SlotOffer,
    free_slots_by_start,
)
from scheduling.domain.vocabulary import AppointmentStatus

PARIS = ZoneInfo("Europe/Paris")
LONG_BEFORE = datetime(2026, 11, 1, tzinfo=UTC)
HALF_HOUR = SlotType(duration=timedelta(minutes=30), buffer=timedelta(0))
DAY_START = datetime(2026, 11, 21, 23, 0, tzinfo=UTC)
SUNDAY = TimeRange(DAY_START, DAY_START + timedelta(days=1))


def _schedule(start: time, end: time) -> ClinicianSchedule:
    rule = AvailabilityWindow(0, start, end, timedelta(minutes=30), date(2026, 1, 1), None)
    return ClinicianSchedule(rules=[rule], time_off=[], appointments=[])


def _search(
    schedules: dict[UUID, ClinicianSchedule], window: TimeRange = SUNDAY
) -> list[SlotOffer] | QueryTooWide:
    return free_slots_by_start(schedules, HALF_HOUR, window, LONG_BEFORE, PARIS)


def _utc(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 22, hour, minute, tzinfo=UTC)


def returns_union_with_clinicians_free_at_each_start_when_two_clinicians_overlap() -> None:
    schedules = {
        UUID(int=2): _schedule(time(9, 30), time(10, 30)),
        UUID(int=1): _schedule(time(9, 0), time(10, 0)),
    }
    assert _search(schedules) == [
        SlotOffer(_utc(8, 0), (UUID(int=1),)),
        SlotOffer(_utc(8, 30), (UUID(int=1), UUID(int=2))),
        SlotOffer(_utc(9, 0), (UUID(int=2),)),
    ]


def returns_empty_when_no_clinicians() -> None:
    assert _search({}) == []


def returns_a_window_of_exactly_31_days_as_offers() -> None:
    window = TimeRange(DAY_START, DAY_START + timedelta(days=MAXIMUM_QUERY_DAYS))
    assert isinstance(_search({UUID(int=1): _schedule(time(9, 0), time(9, 30))}, window), list)


def returns_too_wide_when_window_is_over_31_days() -> None:
    window = TimeRange(DAY_START, DAY_START + timedelta(days=MAXIMUM_QUERY_DAYS, seconds=1))
    assert _search({UUID(int=1): _schedule(time(9, 0), time(9, 30))}, window) == QueryTooWide(
        MAXIMUM_QUERY_DAYS
    )


def returns_offers_sorted_by_start_when_a_later_numbered_clinician_is_free_earlier() -> None:
    schedules = {
        UUID(int=1): _schedule(time(10, 0), time(10, 30)),
        UUID(int=2): _schedule(time(9, 0), time(9, 30)),
    }
    offers = _search(schedules)
    assert isinstance(offers, list)
    assert [offer.start for offer in offers] == [_utc(8, 0), _utc(9, 0)]


def returns_too_wide_when_window_is_32_days() -> None:
    window = TimeRange(DAY_START, DAY_START + timedelta(days=32))
    assert _search({}, window) == QueryTooWide(31)


def returns_no_offer_when_the_only_clinician_has_time_off_then() -> None:
    off = BusyInterval(_utc(8, 0), _utc(8, 30))
    schedule = replace(_schedule(time(9, 0), time(9, 30)), time_off=[off])
    assert _search({UUID(int=1): schedule}) == []


def returns_no_offer_when_the_only_clinician_has_an_active_appointment_then() -> None:
    booked = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.BOOKED)
    schedule = replace(_schedule(time(9, 0), time(9, 30)), appointments=[booked])
    assert _search({UUID(int=1): schedule}) == []


def returns_no_offer_before_now_when_searching() -> None:
    schedules = {UUID(int=1): _schedule(time(9, 0), time(9, 30))}
    offers = free_slots_by_start(schedules, HALF_HOUR, SUNDAY, _utc(8, 1), PARIS)
    assert offers == []


def returns_clinician_uuids_in_uuid_order_when_both_are_free() -> None:
    low, high = UUID(int=3), UUID(int=11)
    schedules = {high: _schedule(time(9, 0), time(9, 30)), low: _schedule(time(9, 0), time(9, 30))}
    assert _search(schedules) == [SlotOffer(_utc(8, 0), (low, high))]
