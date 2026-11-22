"""Task 16, reschedule for the patient: the week of free slots, then a review. The use case
decides; staff are not bound by the patient rules, so a refusal is a conflict or a status."""

from datetime import UTC, date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure
from scheduling.domain.staff_actions import StaffAction, staff_actions_for
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.use_cases.appointment_changes import reschedule_appointment
from scheduling.use_cases.booking_page_data import week_of_slots
from scheduling.views.pages.booking_links import clock_label, day_label, week_from
from scheduling.views.pages.booking_times import week_strip
from scheduling.views.pages.clinician_support import ClinicianPage, appointment_path
from scheduling.views.pages.patient_refusal import (
    STATUS_CHANGED,
    change_refused_page,
    message_page,
)
from scheduling.views.pages.patient_reschedule import (
    TIMES_ACTION_TEXT,
    TIMES_UNAVAILABLE,
    asked_start,
)

BACK_TEXT = "Back to the appointment"


class ReschedulePage(ClinicianPage):
    template_name = "clinician/reschedule_times.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        back = (appointment_path(found.pk), BACK_TEXT)
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
            **week_strip(loaded.value, week_href, slot_href),
        }
        return self.page(request, context)


class RescheduleReviewPage(ClinicianPage):
    template_name = "clinician/reschedule_review.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        starts_at = asked_start(request)
        if isinstance(starts_at, Failure):
            times = (request.path.removesuffix("/review"), TIMES_ACTION_TEXT)
            back = (appointment_path(found.pk), BACK_TEXT)
            return change_refused_page(request, starts_at, self.user, times, back)
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
        }
        return self.page(request, context)

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        starts_at = asked_start(request)
        moved = (
            starts_at
            if isinstance(starts_at, Failure)
            else reschedule_appointment(found.pk, starts_at, self.user)
        )
        if isinstance(moved, Failure):
            times = (request.path.removesuffix("/review"), TIMES_ACTION_TEXT)
            back = (appointment_path(found.pk), BACK_TEXT)
            return change_refused_page(request, moved, self.user, times, back)
        return HttpResponseRedirect(appointment_path(found.pk), status=303)


def when_text(starts_at: datetime, ends_at: datetime, zone: ZoneInfo) -> str:
    day = day_label(starts_at.astimezone(zone).date())
    return f"{day}, {clock_label(starts_at, zone)} to {clock_label(ends_at, zone)}"
