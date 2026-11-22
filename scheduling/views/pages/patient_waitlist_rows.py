"""Task 15: one waitlist entry as the words and links of a list card, in the hospital's zone."""

from zoneinfo import ZoneInfo

from scheduling.domain.vocabulary import WaitlistStatus
from scheduling.models import WaitlistEntry
from scheduling.views.pages.booking_links import clock_label, day_label
from scheduling.views.pages.status_words import WAITLIST_BADGES

WAITLIST_PATH = "/patient/waitlist"


def waitlist_row(entry: WaitlistEntry) -> dict[str, object]:
    appointment_type = entry.appointment_type
    hospital = appointment_type.department.hospital
    zone = ZoneInfo(hospital.time_zone)
    first_day = entry.earliest_at.astimezone(zone).date()
    last_day = entry.latest_at.astimezone(zone).date()
    status = WaitlistStatus(entry.status)
    badge_kind, badge_text = WAITLIST_BADGES[status]
    preferred = entry.preferred_clinician
    return {
        "type_name": appointment_type.name,
        "hospital": hospital.name,
        "window": f"{day_label(first_day)} to {day_label(last_day)} ({hospital.time_zone})",
        "provider": f"{preferred.title} {preferred.user.full_name}"
        if preferred
        else "Any provider",
        "badge_kind": badge_kind,
        "badge_text": badge_text,
        "offer": _offer(entry, zone) if status == WaitlistStatus.OFFERED else None,
        "accept_href": f"{WAITLIST_PATH}/{entry.pk}/accept",
    }


def _offer(entry: WaitlistEntry, zone: ZoneInfo) -> dict[str, str] | None:
    offered = entry.offered_appointment
    if offered is None:
        return None
    clinician = offered.clinician
    return {
        "day": day_label(offered.starts_at.astimezone(zone).date()),
        "starts": clock_label(offered.starts_at, zone),
        "provider": f"{clinician.title} {clinician.user.full_name}",
        "hospital": entry.appointment_type.department.hospital.name,
    }
