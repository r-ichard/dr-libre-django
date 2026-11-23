"""The clinician's agenda for one day in the hospital's zone, and the status actions."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.staff_actions import StaffAction, staff_actions_for
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.domain.workspace_day import day_tiles, group_by_local_hour
from scheduling.models import Appointment, ClinicianProfile
from scheduling.use_cases.appointment_changes import change_status
from scheduling.use_cases.clinician_agenda import day_agenda, next_free_slot
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import clock_label, path_uuid, week_from
from scheduling.views.pages.clinician_support import (
    CLINICIAN_BADGES,
    TODAY_PATH,
    ClinicianPage,
    appointment_path,
)
from scheduling.views.pages.patient_refusal import change_refused_page

RETURN_TODAY = "today"
STATUS_FORM_ACTIONS = (StaffAction.CHECK_IN, StaffAction.COMPLETE, StaffAction.NO_SHOW)
ACTION_LABELS = {
    StaffAction.CHECK_IN: "Check in",
    StaffAction.COMPLETE: "Complete",
    StaffAction.NO_SHOW: "No-show",
}
NO_FREE_SLOT = "None in 14 days"


def day_href(day: date) -> str:
    return f"{TODAY_PATH}?date={day.isoformat()}"


class TodayPage(ClinicianPage):
    template_name = "clinician/today.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        profile = self.profile_or_refusal(request)
        if isinstance(profile, HttpResponse):
            return profile
        time_zone = profile.department.hospital.time_zone
        now = current_request_context().now
        today = now.astimezone(ZoneInfo(time_zone)).date()
        day = week_from(request.GET.get("date", "")) or today
        agenda = day_agenda(profile, day)
        context = {
            "day_text": f"{day:%A} {day.day} {day:%B %Y}",
            "time_zone": time_zone,
            "previous_href": day_href(day - timedelta(days=1)),
            "next_href": day_href(day + timedelta(days=1)),
            "today_href": day_href(today),
            "tiles": _tiles(profile, agenda, now),
            "hours": _hours(agenda, time_zone, day),
        }
        return self.page(request, context)


def _tiles(
    profile: ClinicianProfile, agenda: list[Appointment], now: datetime
) -> list[dict[str, object]]:
    counts = day_tiles(AppointmentStatus(row.status) for row in agenda)
    free = next_free_slot(profile, now)
    zone = ZoneInfo(profile.department.hospital.time_zone)
    free_text = f"{free.astimezone(zone):%a %d %b, %H:%M}" if free else NO_FREE_SLOT
    return [
        {"label": "Appointments", "value": counts.active},
        {"label": "Cancelled", "value": counts.cancelled},
        {"label": "Completed", "value": counts.completed},
        {"label": "No-shows", "value": counts.no_show},
        {"label": "Next free slot", "value": free_text},
    ]


def _hours(agenda: list[Appointment], time_zone: str, day: date) -> list[dict[str, object]]:
    zone = ZoneInfo(time_zone)
    by_start: dict[datetime, list[Appointment]] = {row.starts_at: [] for row in agenda}
    for row in agenda:
        by_start[row.starts_at].append(row)
    groups = group_by_local_hour(list(by_start), time_zone)
    return [
        {
            "heading": f"{hour:02d}:00",
            "rows": [_row(row, zone, day) for start in starts for row in by_start[start]],
        }
        for hour, starts in groups.items()
    ]


def _row(row: Appointment, zone: ZoneInfo, day: date) -> dict[str, object]:
    status = AppointmentStatus(row.status)
    badge_kind, badge_text = CLINICIAN_BADGES[status]
    allowed = staff_actions_for(status)
    base = appointment_path(row.pk)
    return {
        "href": base,
        "patient": row.patient.full_name,
        "time": f"{clock_label(row.starts_at, zone)} to {clock_label(row.ends_at, zone)}",
        "type_name": row.appointment_type.name,
        "room": row.room.name if row.room else "",
        "badge_kind": badge_kind,
        "badge_text": badge_text,
        "forms": [
            {"action": f"{base}/{action.value}", "label": ACTION_LABELS[action]}
            for action in STATUS_FORM_ACTIONS
            if action in allowed
        ],
        "cancel_href": f"{base}/cancel" if StaffAction.CANCEL in allowed else "",
        "reschedule_href": f"{base}/reschedule" if StaffAction.RESCHEDULE in allowed else "",
        "return_date": day.isoformat(),
    }


class StatusActionPage(ClinicianPage):
    """One status change by POST; the page to return to is a name from a fixed list."""

    form_page = "/clinician/appointments/{appointment_id}"
    http_method_names = ["post"]
    target = AppointmentStatus.CHECKED_IN

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        appointment_id = path_uuid(self, "appointment_id")
        changed = change_status(appointment_id, self.target, self.user)
        if isinstance(changed, Failure):
            if changed.code in {FailureCode.NOT_FOUND, FailureCode.FORBIDDEN}:
                return self.refusal_of(request, changed)
            back = (appointment_path(appointment_id), "Back to the appointment")
            return change_refused_page(request, changed, self.user, back_action=back)
        return HttpResponseRedirect(self._return_path(request, appointment_id), status=303)

    @staticmethod
    def _return_path(request: HttpRequest, appointment_id: object) -> str:
        if request.POST.get("return_to") == RETURN_TODAY:
            day = week_from(request.POST.get("date", ""))
            return day_href(day) if day else TODAY_PATH
        return appointment_path(appointment_id)


class CheckInPage(StatusActionPage):
    target = AppointmentStatus.CHECKED_IN


class CompletePage(StatusActionPage):
    target = AppointmentStatus.COMPLETED


class NoShowPage(StatusActionPage):
    target = AppointmentStatus.NO_SHOW
