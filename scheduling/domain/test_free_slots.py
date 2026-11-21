"""Section 5.1: free slots of one clinician, the four steps, in the hospital's local time."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.free_slots import (
    AvailabilityWindow,
    BusyInterval,
    ExistingAppointment,
    SlotType,
    TimeRange,
    free_slots,
)
from scheduling.models.booking import AppointmentStatus

PARIS = ZoneInfo("Europe/Paris")
LONG_BEFORE = datetime(2026, 11, 1, tzinfo=UTC)
SUNDAY = date(2026, 11, 22)
# Paris is UTC+1 in November: local 09:00 is 08:00 UTC.
WHOLE_SUNDAY = TimeRange(
    datetime(2026, 11, 21, 23, 0, tzinfo=UTC), datetime(2026, 11, 22, 23, 0, tzinfo=UTC)
)
HALF_HOUR = SlotType(duration=timedelta(minutes=30), buffer=timedelta(0))


def _rule(
    weekday: int = 0,
    start: time = time(9, 0),
    end: time = time(10, 0),
    step_minutes: int = 15,
    valid_from: date = date(2026, 1, 1),
    valid_to: date | None = None,
) -> AvailabilityWindow:
    return AvailabilityWindow(
        weekday, start, end, timedelta(minutes=step_minutes), valid_from, valid_to
    )


def _utc(hour: int, minute: int = 0, day: int = 22) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def _slots(
    rules: list[AvailabilityWindow],
    appointment_type: SlotType = HALF_HOUR,
    time_off: list[BusyInterval] | None = None,
    appointments: list[ExistingAppointment] | None = None,
    window: TimeRange = WHOLE_SUNDAY,
    now: datetime = LONG_BEFORE,
) -> list[datetime]:
    return free_slots(
        rules, appointment_type, time_off or [], appointments or [], window, now, PARIS
    )


def returns_starts_whose_slot_fits_before_the_rule_end() -> None:
    assert _slots([_rule()]) == [_utc(8, 0), _utc(8, 15), _utc(8, 30)]


def returns_nothing_when_rule_weekday_differs() -> None:
    assert _slots([_rule(weekday=1)]) == []


def returns_slots_when_rule_weekday_is_six_on_a_saturday() -> None:
    saturday = TimeRange(
        datetime(2026, 11, 20, 23, 0, tzinfo=UTC), datetime(2026, 11, 21, 23, 0, tzinfo=UTC)
    )
    assert _slots([_rule(weekday=6)], window=saturday) == [
        _utc(8, 0, day=21),
        _utc(8, 15, day=21),
        _utc(8, 30, day=21),
    ]


def returns_nothing_when_rule_weekday_is_zero_on_a_saturday() -> None:
    saturday = TimeRange(
        datetime(2026, 11, 20, 23, 0, tzinfo=UTC), datetime(2026, 11, 21, 23, 0, tzinfo=UTC)
    )
    assert _slots([_rule(weekday=0)], window=saturday) == []


def returns_slots_when_day_is_the_valid_from_date() -> None:
    assert len(_slots([_rule(valid_from=SUNDAY)])) == 3


def returns_nothing_when_day_is_before_valid_from() -> None:
    assert _slots([_rule(valid_from=SUNDAY + timedelta(days=1))]) == []


def returns_slots_when_day_is_the_valid_to_date() -> None:
    assert len(_slots([_rule(valid_to=SUNDAY)])) == 3


def returns_nothing_when_day_is_after_valid_to() -> None:
    assert _slots([_rule(valid_to=SUNDAY - timedelta(days=1))]) == []


def returns_slot_starting_when_time_off_ends() -> None:
    time_off = [BusyInterval(_utc(8, 0), _utc(8, 30))]
    assert _slots([_rule()], time_off=time_off) == [_utc(8, 30)]


def returns_slot_ending_when_time_off_starts() -> None:
    time_off = [BusyInterval(_utc(8, 0), _utc(8, 30))]
    early = _rule(start=time(8, 30), end=time(9, 30), step_minutes=30)
    assert _slots([early], time_off=time_off) == [_utc(7, 30)]


def returns_slots_after_appointment_end_plus_buffer_of_booked_type() -> None:
    booked_type = SlotType(timedelta(minutes=30), timedelta(minutes=10))
    appointment = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.BOOKED)
    wide = _rule(start=time(9, 0), end=time(10, 15), step_minutes=5)
    assert _slots([wide], booked_type, appointments=[appointment]) == [_utc(8, 40), _utc(8, 45)]


def returns_slot_after_appointment_when_buffer_is_zero() -> None:
    appointment = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.CHECKED_IN)
    assert _slots([_rule()], appointments=[appointment]) == [_utc(8, 30)]


def returns_slot_when_appointment_is_cancelled() -> None:
    appointment = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.CANCELLED)
    assert _slots([_rule(end=time(9, 30))], appointments=[appointment]) == [_utc(8, 0)]


def returns_slot_when_appointment_is_no_show() -> None:
    appointment = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.NO_SHOW)
    assert _slots([_rule(end=time(9, 30))], appointments=[appointment]) == [_utc(8, 0)]


def returns_no_slot_when_completed_appointment_overlaps() -> None:
    appointment = ExistingAppointment(_utc(8, 0), _utc(8, 30), AppointmentStatus.COMPLETED)
    assert _slots([_rule(end=time(9, 30))], appointments=[appointment]) == []


def returns_nothing_before_range_start() -> None:
    window = TimeRange(_utc(8, 15), WHOLE_SUNDAY.ends_at)
    assert _slots([_rule()], window=window) == [_utc(8, 15), _utc(8, 30)]


def returns_nothing_ending_after_range_end() -> None:
    window = TimeRange(WHOLE_SUNDAY.starts_at, _utc(8, 45))
    assert _slots([_rule()], window=window) == [_utc(8, 0), _utc(8, 15)]


def returns_slot_ending_exactly_at_range_end() -> None:
    window = TimeRange(_utc(8, 0), _utc(8, 30))
    assert _slots([_rule(end=time(9, 30))], window=window) == [_utc(8, 0)]


def returns_slot_starting_exactly_at_now_but_not_earlier() -> None:
    assert _slots([_rule()], now=_utc(8, 15)) == [_utc(8, 15), _utc(8, 30)]


def returns_duplicate_start_once_and_sorted_when_two_rules_overlap() -> None:
    later = _rule(start=time(9, 30), end=time(10, 30), step_minutes=30)
    earlier = _rule(start=time(9, 0), end=time(10, 0), step_minutes=30)
    assert _slots([later, earlier]) == [_utc(8, 0), _utc(8, 30), _utc(9, 0)]


def returns_utc_aware_datetimes() -> None:
    assert [slot.utcoffset() for slot in _slots([_rule()])] == [timedelta(0)] * 3


def returns_slots_of_the_local_day_when_range_crosses_local_midnight_only() -> None:
    tuesday_rule = _rule(weekday=2, start=time(1, 0), end=time(2, 0), step_minutes=30)
    window = TimeRange(
        datetime(2026, 6, 1, 22, 30, tzinfo=UTC), datetime(2026, 6, 1, 23, 30, tzinfo=UTC)
    )
    now = datetime(2026, 5, 1, tzinfo=UTC)
    assert _slots([tuesday_rule], window=window, now=now) == [
        datetime(2026, 6, 1, 23, 0, tzinfo=UTC)
    ]


def returns_slot_on_local_day_when_zone_is_west_of_utc_and_window_starts_late_evening() -> None:
    new_york = ZoneInfo("America/New_York")
    # Local Sunday 22:00 is 03:00 UTC on Monday, a different UTC date from the local day.
    window_start = datetime(2026, 11, 22, 22, 0, tzinfo=new_york)
    window = TimeRange(window_start, window_start + timedelta(hours=1))
    late_rule = _rule(start=time(22, 0), end=time(23, 0))
    slots = free_slots([late_rule], HALF_HOUR, [], [], window, LONG_BEFORE, new_york)
    assert slots == [
        datetime(2026, 11, 23, 3, 0, tzinfo=UTC),
        datetime(2026, 11, 23, 3, 15, tzinfo=UTC),
        datetime(2026, 11, 23, 3, 30, tzinfo=UTC),
    ]


def returns_slot_ending_at_range_end_when_type_has_a_buffer() -> None:
    buffered = SlotType(duration=timedelta(minutes=30), buffer=timedelta(minutes=10))
    window = TimeRange(_utc(8, 0), _utc(8, 30))
    assert _slots([_rule(end=time(9, 30))], buffered, window=window) == [_utc(8, 0)]


def returns_slot_when_appointment_starts_where_a_buffered_type_slot_ends() -> None:
    buffered = SlotType(duration=timedelta(minutes=30), buffer=timedelta(minutes=10))
    later = ExistingAppointment(_utc(9, 0), _utc(9, 30), AppointmentStatus.BOOKED)
    assert _slots([_rule(end=time(10, 0))], buffered, appointments=[later]) == [
        _utc(8, 0),
        _utc(8, 15),
        _utc(8, 30),
    ]
