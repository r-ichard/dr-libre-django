"""Section 5.1 as properties: whatever the rules, time off and bookings, offered slots are valid."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scheduling.domain.free_slots import (
    AvailabilityWindow,
    BusyInterval,
    ExistingAppointment,
    SlotType,
    TimeRange,
    free_slots,
)
from scheduling.domain.vocabulary import AppointmentStatus

ZONES = [ZoneInfo(name) for name in ("UTC", "America/New_York", "Australia/Sydney")]
EPOCH = datetime(2026, 3, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
PROPERTY_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@dataclass(frozen=True)
class Scenario:
    rules: list[AvailabilityWindow]
    time_off: list[BusyInterval]
    appointments: list[ExistingAppointment]
    slot_type: SlotType
    window: TimeRange
    now: datetime
    zone: ZoneInfo


instants = st.integers(0, 60 * 24 * 14).map(lambda minutes: EPOCH + minutes * MINUTE)
early_instants = st.integers(0, 60 * 24 * 3).map(lambda minutes: EPOCH + minutes * MINUTE)
rule_spans = st.tuples(st.integers(0, 12 * 60), st.integers(60, 11 * 60))
rules = st.builds(
    AvailabilityWindow,
    weekday=st.integers(0, 6),
    start_time=rule_spans.map(lambda span: time(span[0] // 60, span[0] % 60)),
    end_time=rule_spans.map(lambda span: time((span[0] + span[1]) // 60, 0)),
    slot_step=st.integers(15, 120).map(lambda minutes: timedelta(minutes=minutes)),
    valid_from=st.integers(0, 5).map(lambda days: date(2026, 3, 1) + timedelta(days=days)),
    valid_to=st.none()
    | st.integers(8, 40).map(lambda days: date(2026, 3, 1) + timedelta(days=days)),
)
intervals = st.tuples(instants, st.integers(1, 600)).map(
    lambda pair: (pair[0], pair[0] + pair[1] * MINUTE)
)
slot_types = st.builds(
    SlotType,
    duration=st.integers(5, 120).map(lambda minutes: timedelta(minutes=minutes)),
    buffer=st.integers(0, 30).map(lambda minutes: timedelta(minutes=minutes)),
)
windows = st.tuples(early_instants, st.integers(60 * 24 * 3, 60 * 24 * 10)).map(
    lambda pair: TimeRange(pair[0], pair[0] + pair[1] * MINUTE)
)
appointments = st.tuples(intervals, st.sampled_from(list(AppointmentStatus))).map(
    lambda pair: ExistingAppointment(pair[0][0], pair[0][1], pair[1])
)
scenario = st.builds(
    Scenario,
    rules=st.lists(rules, min_size=3, max_size=7),
    time_off=st.lists(intervals.map(lambda pair: BusyInterval(*pair)), max_size=6),
    appointments=st.lists(appointments, max_size=6),
    slot_type=slot_types,
    window=windows,
    now=early_instants,
    zone=st.sampled_from(ZONES),
)


def _offered(case: Scenario) -> list[datetime]:
    return free_slots(
        case.rules,
        case.slot_type,
        case.time_off,
        case.appointments,
        case.window,
        case.now,
        case.zone,
    )


def _inside_a_rule_window(case: Scenario, start: datetime) -> bool:
    zone = case.zone
    local_start = start.astimezone(zone)
    local_end = (start + case.slot_type.duration).astimezone(zone)
    weekday = local_start.date().isoweekday() % 7
    return any(
        rule.weekday == weekday
        and rule.valid_from <= local_start.date()
        and (rule.valid_to is None or local_start.date() <= rule.valid_to)
        and rule.start_time <= local_start.time()
        and local_end.date() == local_start.date()
        and local_end.time() <= rule.end_time
        for rule in case.rules
    )


@PROPERTY_SETTINGS
@given(scenario)
def returns_slots_inside_a_rule_window_when_rules_are_generated(case: Scenario) -> None:
    assert [s for s in _offered(case) if not _inside_a_rule_window(case, s)] == []


@PROPERTY_SETTINGS
@given(scenario)
def returns_slots_inside_the_query_range_and_not_in_the_past_when_generated(case: Scenario) -> None:
    duration = case.slot_type.duration
    window = case.window
    assert [
        s
        for s in _offered(case)
        if s < window.starts_at or s + duration > window.ends_at or s < case.now
    ] == []


@PROPERTY_SETTINGS
@given(scenario)
def returns_no_slot_overlapping_time_off_or_buffered_active_appointments(case: Scenario) -> None:
    duration, buffer = case.slot_type.duration, case.slot_type.buffer
    blocked = [(off.starts_at, off.ends_at) for off in case.time_off] + [
        (booked.starts_at, booked.ends_at + buffer)
        for booked in case.appointments
        if booked.status not in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)
    ]
    assert [
        s
        for s in _offered(case)
        if any(s < stop and begin < s + duration for begin, stop in blocked)
    ] == []


@PROPERTY_SETTINGS
@given(scenario)
def returns_strictly_increasing_slots_when_generated(case: Scenario) -> None:
    offered = _offered(case)
    assert all(earlier < later for earlier, later in zip(offered, offered[1:], strict=False))
