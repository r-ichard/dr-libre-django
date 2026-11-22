"""Task 14: one appointment as the words and links of a list row, in the hospital's zone."""

from datetime import datetime
from zoneinfo import ZoneInfo

from scheduling.domain.portal_options import appointment_options, expects_change_hint
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.views.pages.booking_links import address_of, clock_label, day_label
from scheduling.views.pages.status_words import APPOINTMENT_BADGES

LIST_PATH = "/patient/appointments"


def appointment_row(appointment: Appointment, now: datetime) -> dict[str, object]:
    hospital = appointment.appointment_type.department.hospital
    time_zone = ZoneInfo(hospital.time_zone)
    clinician = appointment.clinician
    status = AppointmentStatus(appointment.status)
    options = appointment_options(status, appointment.starts_at, now)
    badge_kind, badge_text = APPOINTMENT_BADGES[status]
    base = f"{LIST_PATH}/{appointment.pk}"
    return {
        "provider": f"{clinician.title} {clinician.user.full_name}",
        "specialty": clinician.specialty.name,
        "day": day_label(appointment.starts_at.astimezone(time_zone).date()),
        "starts": clock_label(appointment.starts_at, time_zone),
        "ends": clock_label(appointment.ends_at, time_zone),
        "time_zone": hospital.time_zone,
        "hospital": hospital.name,
        "address": address_of(hospital),
        "phone": hospital.phone,
        "department": appointment.appointment_type.department.name,
        "room": appointment.room.name if appointment.room else "",
        "type_name": appointment.appointment_type.name,
        "badge_kind": badge_kind,
        "badge_text": badge_text,
        "reason": appointment.patient_reason,
        "options": options,
        "expects_hint": expects_change_hint(status),
        "cancelled_note": options.cancel.reason if status == AppointmentStatus.CANCELLED else "",
        "cancel_href": f"{base}/cancel",
        "reschedule_href": f"{base}/reschedule",
        "calendar_href": (
            f"/appointments/{appointment.pk}/calendar.ics"
            if status != AppointmentStatus.CANCELLED
            else ""
        ),
    }
