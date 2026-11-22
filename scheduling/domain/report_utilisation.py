"""Section 13: utilisation, minutes of active appointments over the minutes clinicians could work.

A rule's hours are wall clock in its hospital's zone; each window is turned into UTC before it is
measured, so a day with a clock change has its real length."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from scheduling.domain.appointment_status import is_active
from scheduling.domain.report_figures import (
    NOT_AVAILABLE,
    ReportedVisit,
    hospital_day,
    percent_text,
)

DAYS_PER_WEEK = 7
SECONDS_PER_MINUTE = 60

Window = tuple[datetime, datetime]


@dataclass(frozen=True)
class RuleHours:
    clinician_id: str
    weekday: int
    start_time: time
    end_time: time
    valid_from: date
    valid_to: date | None
    time_zone: str


@dataclass(frozen=True)
class OffPeriod:
    clinician_id: str
    starts_at: datetime
    ends_at: datetime


def utilisation(
    visits: list[ReportedVisit], rules: list[RuleHours], off: list[OffPeriod], days: list[date]
) -> str:
    available = available_minutes(rules, off, days)
    if available == 0:
        return NOT_AVAILABLE
    return percent_text(_booked_minutes(visits, days), available)


def available_minutes(rules: list[RuleHours], off: list[OffPeriod], days: list[date]) -> int:
    seconds = 0
    for clinician_id in {rule.clinician_id for rule in rules}:
        windows = [
            window
            for rule in rules
            if rule.clinician_id == clinician_id
            for window in _rule_windows(rule, days)
        ]
        gaps = _merged(
            [
                (period.starts_at, period.ends_at)
                for period in off
                if period.clinician_id == clinician_id
            ]
        )
        seconds += sum(_length(window) - _overlap(window, gaps) for window in windows)
    return seconds // SECONDS_PER_MINUTE


def _booked_minutes(visits: list[ReportedVisit], days: list[date]) -> int:
    seconds = sum(
        _length((visit.starts_at, visit.ends_at))
        for visit in visits
        if is_active(visit.status) and hospital_day(visit) in days
    )
    return seconds // SECONDS_PER_MINUTE


def _rule_windows(rule: RuleHours, days: list[date]) -> list[Window]:
    zone = ZoneInfo(rule.time_zone)
    return [
        (
            datetime.combine(day, rule.start_time, tzinfo=zone).astimezone(UTC),
            datetime.combine(day, rule.end_time, tzinfo=zone).astimezone(UTC),
        )
        for day in days
        if day.isoweekday() % DAYS_PER_WEEK == rule.weekday
        and rule.valid_from <= day
        and (rule.valid_to is None or day <= rule.valid_to)
    ]


def _merged(periods: list[Window]) -> list[Window]:
    merged: list[Window] = []
    for start, end in sorted(periods):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _overlap(window: Window, gaps: list[Window]) -> int:
    return sum(max(0, _length((max(window[0], start), min(window[1], end)))) for start, end in gaps)


def _length(window: Window) -> int:
    return int((window[1] - window[0]).total_seconds())
