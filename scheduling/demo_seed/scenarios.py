"""The moving demo world: bookings placed by day offset from the day of the run. Pure data.

Every appointment has its own local starting hour, so a later run never trips the overlap
constraints."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.domain.vocabulary import AppointmentSource as Source
from scheduling.domain.vocabulary import AppointmentStatus as Status
from scheduling.models.booking import NotificationKind as Kind
from scheduling.models.booking import WaitlistStatus

AppointmentKey = tuple[str, str, str]
WaitlistKey = tuple[str, str]


@dataclass(frozen=True)
class AppointmentSeed:
    patient_email: str
    clinician_email: str
    type_code: str
    day_offset: int
    hour: int
    status: Status
    source: Source
    from_waitlist: bool = False

    @property
    def key(self) -> AppointmentKey:
        return (self.patient_email, self.clinician_email, self.type_code)


@dataclass(frozen=True)
class WaitlistSeed:
    patient_email: str
    type_code: str
    earliest_offset: int
    latest_offset: int
    status: WaitlistStatus
    preferred_clinician_email: str | None = None
    offered: AppointmentKey | None = None

    @property
    def key(self) -> WaitlistKey:
        return (self.patient_email, self.type_code)


@dataclass(frozen=True)
class TimeOffSeed:
    clinician_email: str
    reason: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class NotificationSeed:
    recipient_email: str
    kind: Kind
    title: str
    is_read: bool
    appointment: AppointmentKey | None = None
    waitlist: WaitlistKey | None = None


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

APPOINTMENTS = (
    AppointmentSeed(BERLIN_PATIENT, HEART, CONSULT, -14, 9, Status.COMPLETED, Source.ONLINE),
    AppointmentSeed(BERLIN_PATIENT, HEART, PHONE, -3, 10, Status.NO_SHOW, Source.STAFF),
    AppointmentSeed(
        BERLIN_PATIENT, HEART_SECOND, CONSULT, 0, 11, Status.CHECKED_IN, Source.ROUND_ROBIN
    ),
    AppointmentSeed(BERLIN_OTHER, HEART, CONSULT, 2, 12, Status.BOOKED, Source.ONLINE),
    AppointmentSeed(BERLIN_OTHER, SKIN, SKIN_CHECK, 5, 13, Status.CONFIRMED, Source.STAFF),
    AppointmentSeed(BERLIN_OTHER, HEART_SECOND, PHONE, 1, 14, Status.CANCELLED, Source.ONLINE),
    AppointmentSeed(NEW_YORK_PATIENT, GENERAL, CHECKUP, -10, 15, Status.COMPLETED, Source.STAFF),
    AppointmentSeed(NEW_YORK_PATIENT, GENERAL, VIDEO, 0, 16, Status.BOOKED, Source.ROUND_ROBIN),
    AppointmentSeed(NEW_YORK_OTHER, GENERAL, CHECKUP, 3, 17, Status.CONFIRMED, Source.ONLINE),
    AppointmentSeed(NEW_YORK_OTHER, GENERAL, VIDEO, -6, 18, Status.CANCELLED, Source.STAFF),
    AppointmentSeed(SYDNEY_PATIENT, CHILD, PAEDIATRIC, -20, 19, Status.COMPLETED, Source.ONLINE),
    AppointmentSeed(SYDNEY_OTHER, CHILD, PAEDIATRIC, 1, 20, Status.BOOKED, Source.STAFF, True),
)
_OFFERED_SLOT = (BERLIN_OTHER, HEART_SECOND, PHONE)

WAITLIST_ENTRIES = (
    WaitlistSeed(BERLIN_OTHER, CONSULT, 1, 14, WaitlistStatus.WAITING, HEART),
    WaitlistSeed(BERLIN_PATIENT, PHONE, 1, 7, WaitlistStatus.OFFERED, offered=_OFFERED_SLOT),
    WaitlistSeed(SYDNEY_OTHER, PAEDIATRIC, -3, 10, WaitlistStatus.BOOKED),
    WaitlistSeed(NEW_YORK_OTHER, CHECKUP, -20, -5, WaitlistStatus.EXPIRED),
)

TIME_OFF = (
    TimeOffSeed(HEART, "Cardiology conference", 10, 12),
    TimeOffSeed(CHILD, "Annual leave", 20, 27),
)

NOTIFICATIONS = (
    NotificationSeed(BERLIN_OTHER, Kind.APPOINTMENT_REMINDER, "Appointment reminder", False,
                     appointment=(BERLIN_OTHER, HEART, CONSULT)),
    NotificationSeed(NEW_YORK_PATIENT, Kind.APPOINTMENT_REMINDER, "Appointment reminder", True,
                     appointment=(NEW_YORK_PATIENT, GENERAL, VIDEO)),
    NotificationSeed(BERLIN_OTHER, Kind.APPOINTMENT_CANCELLED, "Appointment cancelled", False,
                     appointment=_OFFERED_SLOT),
    NotificationSeed(BERLIN_PATIENT, Kind.WAITLIST_OFFERED, "A slot is free for you", False,
                     waitlist=(BERLIN_PATIENT, PHONE)),
    NotificationSeed(SYDNEY_OTHER, Kind.WAITLIST_BOOKED, "Your waitlist booking is confirmed", True,
                     waitlist=(SYDNEY_OTHER, PAEDIATRIC)),
    NotificationSeed(NEW_YORK_OTHER, Kind.SCHEDULE_CHANGED, "Your schedule changed", True,
                     appointment=(NEW_YORK_OTHER, GENERAL, VIDEO)),
)  # fmt: skip


def starts_at_for(now: datetime, zone: ZoneInfo, day_offset: int, hour: int) -> datetime:
    local_day = now.astimezone(zone).date() + timedelta(days=day_offset)
    return datetime.combine(local_day, time(hour), tzinfo=zone).astimezone(UTC)
