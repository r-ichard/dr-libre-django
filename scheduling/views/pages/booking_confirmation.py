"""The booking confirmation and calendar file: only the appointment's patient may open either."""

from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse
from django.utils.cache import add_never_cache_headers

from scheduling.domain.calendar_event import CalendarEvent, build_calendar_text
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import (
    PATIENT_PATH,
    address_of,
    clock_label,
    day_label,
)
from scheduling.views.pages.patient_appointments import OwnAppointmentPage

CALENDAR_TYPE = "text/calendar; charset=utf-8"


class _PatientAppointmentPage(OwnAppointmentPage):
    def live_appointment_or_refusal(self, request: HttpRequest) -> Appointment | HttpResponse:
        """Section 12.3: someone else's record is forbidden; a cancelled one is gone."""
        found = self.appointment_or_refusal(request)
        if isinstance(found, Appointment) and found.status == AppointmentStatus.CANCELLED:
            raise Http404
        return found


class ConfirmationPage(_PatientAppointmentPage):
    template_name = "booking/confirmation.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        appointment = self.live_appointment_or_refusal(request)
        if isinstance(appointment, HttpResponse):
            return appointment
        hospital = appointment.appointment_type.department.hospital
        time_zone = ZoneInfo(hospital.time_zone)
        clinician = appointment.clinician
        context = {
            "provider": f"{clinician.title} {clinician.user.full_name}",
            "specialty": clinician.specialty.name,
            "day": day_label(appointment.starts_at.astimezone(time_zone).date()),
            "starts": clock_label(appointment.starts_at, time_zone),
            "ends": clock_label(appointment.ends_at, time_zone),
            "time_zone": hospital.time_zone,
            "hospital": hospital.name,
            "address": address_of(hospital),
            "department": appointment.appointment_type.department.name,
            "room": appointment.room.name if appointment.room else "",
            "type_name": appointment.appointment_type.name,
            "calendar_href": f"/appointments/{appointment.pk}/calendar.ics",
            "patient_path": PATIENT_PATH,
        }
        return self.page(request, context)


class CalendarFile(_PatientAppointmentPage):
    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        appointment = self.live_appointment_or_refusal(request)
        if isinstance(appointment, HttpResponse):
            return appointment
        hospital = appointment.appointment_type.department.hospital
        clinician = appointment.clinician
        event = CalendarEvent(
            uid=f"{appointment.pk}@drlibre",
            starts_at=appointment.starts_at,
            ends_at=appointment.ends_at,
            stamped_at=current_request_context().now,
            summary=f"{clinician.title} {clinician.user.full_name}: "
            f"{appointment.appointment_type.name}",
            location=f"{hospital.name}, {address_of(hospital)}",
        )
        response = HttpResponse(build_calendar_text(event), content_type=CALENDAR_TYPE)
        response["Content-Disposition"] = 'attachment; filename="appointment.ics"'
        add_never_cache_headers(response)
        return response
