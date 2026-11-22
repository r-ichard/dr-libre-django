"""Section 10: an admin moves a BOOKED or CONFIRMED appointment from the week strip. The same
two steps as the clinician's; only the guard and the paths differ. The use case decides."""

from datetime import UTC, date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.staff_actions import StaffAction, staff_actions_for
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.use_cases.appointment_changes import reschedule_appointment
from scheduling.use_cases.booking_page_data import week_of_slots
from scheduling.views.pages.admin_appointments import (
    BACK_TO_APPOINTMENT,
    AdminAppointmentPage,
    appointment_path,
)
from scheduling.views.pages.admin_notices import admin_redirect
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.booking_links import week_from
from scheduling.views.pages.booking_times import week_strip
from scheduling.views.pages.clinician_reschedule import when_text
from scheduling.views.pages.patient_refusal import STATUS_CHANGED, message_page
from scheduling.views.pages.patient_reschedule import (
    TIMES_ACTION_TEXT,
    TIMES_UNAVAILABLE,
    asked_start,
)

TIMES_CODES = {FailureCode.CONFLICT, FailureCode.NO_ROOM_AVAILABLE, FailureCode.RULE_VIOLATION}


class RescheduleTimesPage(AdminAppointmentPage):
    template_name = "admin/reschedule_times.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_404()
        back = (appointment_path(found.pk), BACK_TO_APPOINTMENT)
        if StaffAction.RESCHEDULE not in staff_actions_for(AppointmentStatus(found.status)):
            return message_page(request, self.user, STATUS_CHANGED, back, 409)
        loaded = week_of_slots(
            found.appointment_type_id,
            found.clinician_id,
            week_from(request.GET.get("week", "")),
            online_only=False,
        )
        if isinstance(loaded, Failure):
            return message_page(request, self.user, TIMES_UNAVAILABLE, back, 404)
        base = request.path

        def week_href(week_start: date) -> str:
            return f"{base}?{urlencode({'week': week_start.isoformat()})}"

        def slot_href(starts_at: datetime) -> str:
            stamp = starts_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            return f"{base}/review?{urlencode({'starts_at': stamp}, safe=':')}"

        context = {
            "patient": found.patient.full_name,
            "back_path": back[0],
            "current": "appointments",
            **week_strip(loaded.value, week_href, slot_href),
        }
        return self.page(request, context)


class RescheduleReviewPage(AdminAppointmentPage):
    template_name = "admin/reschedule_review.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_404()
        starts_at = asked_start(request)
        if isinstance(starts_at, Failure):
            return self._refused(request, found, starts_at)
        zone = ZoneInfo(found.appointment_type.department.hospital.time_zone)
        ends_at = starts_at + (found.ends_at - found.starts_at)
        context = {
            "patient": found.patient.full_name,
            "type_name": found.appointment_type.name,
            "old_text": when_text(found.starts_at, found.ends_at, zone),
            "new_text": when_text(starts_at, ends_at, zone),
            "time_zone": str(zone),
            "action": request.get_full_path(),
            "times_path": request.path.removesuffix("/review"),
            "current": "appointments",
        }
        return self.page(request, context)

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_404()
        starts_at = asked_start(request)
        moved = (
            starts_at
            if isinstance(starts_at, Failure)
            else reschedule_appointment(found.pk, starts_at, self.user)
        )
        if isinstance(moved, Failure):
            return self._refused(request, found, moved)
        return admin_redirect(appointment_path(found.pk), "rescheduled", found.pk)

    def _refused(self, request: HttpRequest, found: Appointment, failure: Failure) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        times = (request.path.removesuffix("/review"), TIMES_ACTION_TEXT)
        back = (appointment_path(found.pk), BACK_TO_APPOINTMENT)
        target = times if failure.code in TIMES_CODES else back
        return admin_refused_page(request, self.user, failure, target)


def admin_reschedule_routes() -> list[URLPattern]:
    one = "admin-console/appointments/<uuid:appointment_id>/reschedule"
    return [
        path(one, RescheduleTimesPage.as_view()),
        path(f"{one}/review", RescheduleReviewPage.as_view()),
    ]
