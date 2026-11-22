"""The moving demo world: bookings placed by working-day offset from the day of the run. Pure data.

A start is a whole local hour from 09:00 to 16:00 on Monday to Friday, inside every clinician's
rules, and no two seeds of one clinician touch."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.vocabulary import AppointmentSource as Source
from scheduling.domain.vocabulary import AppointmentStatus as Status

WEEKEND_START = 5
FINISHED_STATUSES = (Status.COMPLETED, Status.NO_SHOW, Status.CHECKED_IN)


@dataclass(frozen=True)
class AppointmentSeed:
    patient_email: str
    clinician_email: str
    type_code: str
    day_offset: int
    hour: int
    status: Status
    source: Source


@dataclass(frozen=True)
class WaitlistSeed:
    patient_email: str
    type_code: str
    earliest_offset: int
    latest_offset: int
    preferred_clinician_email: str | None = None
    joined_offset: int | None = None
    accepts: bool = False


@dataclass(frozen=True)
class TimeOffSeed:
    clinician_email: str
    reason: str
    start_offset: int
    end_offset: int


BERLIN_PATIENT = "patient@example.test"
BERLIN_OTHER = "passwordless@example.test"
NEW_YORK_PATIENT = "patient.three@example.test"
NEW_YORK_OTHER = "patient.four@example.test"
SYDNEY_PATIENT = "patient.five@example.test"
SYDNEY_OTHER = "patient.six@example.test"
HEART = "clinician@example.test"
HEART_SECOND = "clinician.heart@example.test"
SKIN = "clinician.skin@example.test"
GENERAL = "clinician.general@example.test"
CHILD = "clinician.child@example.test"
CONSULT = "demo-cardiology-consult"
PHONE = "demo-cardiology-phone"
SKIN_CHECK = "demo-skin-check"
CHECKUP = "demo-general-checkup"
VIDEO = "demo-general-video"
PAEDIATRIC = "demo-paediatric-visit"

# Order matters: a round robin seed follows the seed that keeps the other clinician busy, and a
# cancelled seed follows the waitlist entry it should free a slot for (see booking.py).
APPOINTMENTS = (
    AppointmentSeed(BERLIN_PATIENT, HEART, CONSULT, -14, 9, Status.COMPLETED, Source.ONLINE),
    AppointmentSeed(BERLIN_OTHER, HEART, CONSULT, 0, 9, Status.COMPLETED, Source.STAFF),
    AppointmentSeed(BERLIN_PATIENT, HEART, PHONE, 0, 10, Status.NO_SHOW, Source.STAFF),
    AppointmentSeed(BERLIN_PATIENT, HEART, CONSULT, 0, 11, Status.CHECKED_IN, Source.STAFF),
    AppointmentSeed(BERLIN_OTHER, HEART, PHONE, 0, 13, Status.BOOKED, Source.ONLINE),
    AppointmentSeed(
        BERLIN_PATIENT, HEART_SECOND, CONSULT, 0, 13, Status.BOOKED, Source.ROUND_ROBIN
    ),
    AppointmentSeed(BERLIN_OTHER, HEART, PHONE, 0, 14, Status.CANCELLED, Source.STAFF),
    AppointmentSeed(BERLIN_OTHER, HEART, CONSULT, 2, 12, Status.BOOKED, Source.ONLINE),
    AppointmentSeed(BERLIN_OTHER, SKIN, SKIN_CHECK, 5, 13, Status.BOOKED, Source.STAFF),
    AppointmentSeed(BERLIN_OTHER, HEART_SECOND, PHONE, 1, 14, Status.CANCELLED, Source.ONLINE),
    AppointmentSeed(NEW_YORK_PATIENT, GENERAL, CHECKUP, -10, 15, Status.COMPLETED, Source.STAFF),
    AppointmentSeed(NEW_YORK_PATIENT, GENERAL, VIDEO, 0, 16, Status.BOOKED, Source.STAFF),
    AppointmentSeed(NEW_YORK_OTHER, GENERAL, CHECKUP, 3, 10, Status.BOOKED, Source.ONLINE),
    AppointmentSeed(NEW_YORK_OTHER, GENERAL, VIDEO, -6, 12, Status.CANCELLED, Source.STAFF),
    AppointmentSeed(SYDNEY_PATIENT, CHILD, PAEDIATRIC, -20, 9, Status.COMPLETED, Source.ONLINE),
    AppointmentSeed(SYDNEY_PATIENT, CHILD, PAEDIATRIC, 2, 10, Status.CANCELLED, Source.ONLINE),
)

WAITLIST_ENTRIES = (
    WaitlistSeed(BERLIN_OTHER, CONSULT, 1, 14, HEART),
    WaitlistSeed(BERLIN_PATIENT, PHONE, 1, 7),
    WaitlistSeed(SYDNEY_OTHER, PAEDIATRIC, -3, 10, accepts=True),
    WaitlistSeed(NEW_YORK_OTHER, CHECKUP, -20, -5, joined_offset=-21),
)

TIME_OFF = (
    TimeOffSeed(HEART, "Cardiology conference", 10, 12),
    TimeOffSeed(CHILD, "Annual leave", 20, 27),
)


def working_day(now: datetime, zone: ZoneInfo, offset: int, finished: bool = False) -> date:
    """Today in the zone, moved by `offset` working days. On a weekend a finished visit starts
    from the last working day and any other from the next one."""
    day = now.astimezone(zone).date()
    start_step = timedelta(days=-1 if finished or offset < 0 else 1)
    while day.weekday() >= WEEKEND_START:
        day += start_step
    step = timedelta(days=1 if offset > 0 else -1)
    for _ in range(abs(offset)):
        day += step
        while day.weekday() >= WEEKEND_START:
            day += step
    return day


def starts_at_for(now: datetime, zone: ZoneInfo, seed: AppointmentSeed) -> datetime:
    finished = seed.status in FINISHED_STATUSES
    day = working_day(now, zone, seed.day_offset, finished)
    return datetime.combine(day, time(seed.hour), tzinfo=zone).astimezone(UTC)


def local_midnight(now: datetime, zone: ZoneInfo, day_offset: int) -> datetime:
    """Midnight starting the calendar day `day_offset` days from today in the zone, in UTC."""
    day = now.astimezone(zone).date() + timedelta(days=day_offset)
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
