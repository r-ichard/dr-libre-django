"""What every booking page says about the chosen appointment, in the hospital's own words."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduling.models import Hospital
from scheduling.use_cases.booking_page_data import SlotChoice
from scheduling.views.pages.booking_links import address_of, clock_label, day_label

FIRST_AVAILABLE = "First available provider"


@dataclass(frozen=True)
class SlotSummary:
    type_name: str
    duration: str
    provider: str
    hospital: str
    address: str
    time_zone: str
    when: str


def duration_label(minutes: int) -> str:
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def slot_summary(choice: SlotChoice, starts_at: datetime | None) -> SlotSummary:
    appointment_type = choice.appointment_type
    hospital: Hospital = appointment_type.department.hospital
    time_zone = ZoneInfo(hospital.time_zone)
    clinician = choice.clinician
    provider = f"{clinician.title} {clinician.user.full_name}" if clinician else FIRST_AVAILABLE
    when = ""
    if starts_at is not None:
        local = starts_at.astimezone(time_zone)
        when = f"{day_label(local.date())}, {clock_label(starts_at, time_zone)}"
    return SlotSummary(
        appointment_type.name,
        duration_label(appointment_type.duration_minutes),
        provider,
        hospital.name,
        address_of(hospital),
        hospital.time_zone,
        when,
    )
