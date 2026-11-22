"""Section 13: the dashboard figures, each as the table defines it. Pure."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, WaitlistStatus

BUSIEST_LIMIT = 5
FULL_BAR_WIDTH = 100
NOT_AVAILABLE = "n/a"
ONLINE_SOURCES = frozenset({AppointmentSource.ONLINE, AppointmentSource.ROUND_ROBIN})
WAITING_STATUSES = frozenset({WaitlistStatus.WAITING, WaitlistStatus.OFFERED})


@dataclass(frozen=True)
class ReportedVisit:
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    source: AppointmentSource
    time_zone: str
    clinician_id: str


@dataclass(frozen=True)
class DayCount:
    day: date
    count: int
    bar_width: int


@dataclass(frozen=True)
class BusyClinician:
    clinician_id: str
    count: int


def hospital_day(visit: ReportedVisit) -> date:
    return visit.starts_at.astimezone(ZoneInfo(visit.time_zone)).date()


def percent_text(part: int, whole: int) -> str:
    if whole == 0:
        return NOT_AVAILABLE
    return f"{(200 * part + whole) // (2 * whole)} %"


def _kept(visits: list[ReportedVisit]) -> list[ReportedVisit]:
    return [visit for visit in visits if visit.status != AppointmentStatus.CANCELLED]


def appointment_count(visits: list[ReportedVisit]) -> int:
    return len(_kept(visits))


def cancellation_count(visits: list[ReportedVisit]) -> int:
    return len(visits) - len(_kept(visits))


def no_show_rate(visits: list[ReportedVisit]) -> str:
    kept = _kept(visits)
    missed = sum(1 for visit in kept if visit.status == AppointmentStatus.NO_SHOW)
    return percent_text(missed, len(kept))


def online_share(visits: list[ReportedVisit]) -> str:
    kept = _kept(visits)
    online = sum(1 for visit in kept if visit.source in ONLINE_SOURCES)
    return percent_text(online, len(kept))


def waitlist_size(statuses: list[WaitlistStatus]) -> int:
    return sum(1 for status in statuses if status in WAITING_STATUSES)


def appointments_per_day(visits: list[ReportedVisit], days: list[date]) -> list[DayCount]:
    per_day = Counter(hospital_day(visit) for visit in _kept(visits))
    busiest_day = max((per_day[day] for day in days), default=0)
    return [
        DayCount(
            day, per_day[day], per_day[day] * FULL_BAR_WIDTH // busiest_day if busiest_day else 0
        )
        for day in days
    ]


def busiest_clinicians(visits: list[ReportedVisit]) -> list[BusyClinician]:
    per_clinician = Counter(visit.clinician_id for visit in _kept(visits))
    ranked = sorted(per_clinician.items(), key=lambda item: (-item[1], item[0]))
    return [BusyClinician(name, count) for name, count in ranked[:BUSIEST_LIMIT]]
