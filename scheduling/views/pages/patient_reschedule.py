"""Task 14: reschedule steps: the week of free slots for the same provider and type, then a
review of the old and the new time. The use case decides; these pages only ask."""

from datetime import UTC, date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.booking_rules import BookingRule
from scheduling.domain.failure import Failure
from scheduling.models import Appointment
from scheduling.use_cases.appointment_changes import reschedule_appointment
from scheduling.use_cases.booking_page_data import week_of_slots
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import (
    clock_label,
    day_label,
    instant_from,
    is_instant,
    week_from,
)
from scheduling.views.pages.booking_times import week_strip
from scheduling.views.pages.patient_appointments import OwnAppointmentPage
from scheduling.views.pages.patient_refusal import (
    LIST_ACTION,
    blocked_page_or_none,
    change_refused_page,
    message_page,
)
from scheduling.views.pages.patient_rows import LIST_PATH, appointment_row
from scheduling.views.pages.portal_forms import redirect_with_notice

TIMES_UNAVAILABLE = "We could not load times for this appointment."
TIMES_ACTION_TEXT = "See the refreshed times"


class ReschedulePage(OwnAppointmentPage):
    template_name = "patient/reschedule_times.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        blocked = blocked_page_or_none(request, found, self.user, "reschedule")
        if blocked is not None:
            return blocked
        base = request.path
        loaded = week_of_slots(
            found.appointment_type_id,
            found.clinician_id,
            week_from(request.GET.get("week", "")),
            online_only=True,
        )
        if isinstance(loaded, Failure):
            return message_page(request, self.user, TIMES_UNAVAILABLE, LIST_ACTION, 404)

        def week_href(week_start: date) -> str:
            return f"{base}?{urlencode({'week': week_start.isoformat()})}"

        def slot_href(starts_at: datetime) -> str:
            stamp = starts_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            return f"{base}/review?{urlencode({'starts_at': stamp}, safe=':')}"

        context = {
            "row": appointment_row(found, current_request_context().now),
            **week_strip(loaded.value, week_href, slot_href),
        }
        return self.page(request, context)


class RescheduleReviewPage(OwnAppointmentPage):
    template_name = "patient/reschedule_review.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        blocked = blocked_page_or_none(request, found, self.user, "reschedule")
        if blocked is not None:
            return blocked
        starts_at = asked_start(request)
        if isinstance(starts_at, Failure):
            times = (request.path.removesuffix("/review"), TIMES_ACTION_TEXT)
            return change_refused_page(request, starts_at, self.user, times)
        return self._review(request, found, starts_at)

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
            return change_refused_page(request, moved, self.user, times)
        return redirect_with_notice(LIST_PATH, "rescheduled")

    def _review(
        self, request: HttpRequest, appointment: Appointment, starts_at: datetime
    ) -> HttpResponse:
        current = appointment_row(appointment, current_request_context().now)
        time_zone = ZoneInfo(str(current["time_zone"]))
        ends_at = starts_at + (appointment.ends_at - appointment.starts_at)
        context = {
            "current": current,
            "new_day": day_label(starts_at.astimezone(time_zone).date()),
            "new_starts": clock_label(starts_at, time_zone),
            "new_ends": clock_label(ends_at, time_zone),
            "action": request.get_full_path(),
            "times_path": request.path.removesuffix("/review"),
        }
        return self.page(request, context)


def asked_start(request: HttpRequest) -> datetime | Failure:
    """A time out of range was never offered: a refusal value. A value that is no time is a 404."""
    raw = request.GET.get("starts_at", "")
    starts_at = instant_from(raw)
    if starts_at is not None:
        return starts_at
    if is_instant(raw):
        return Failure.rule_violation([BookingRule.OUTSIDE_AVAILABILITY])
    raise Http404
