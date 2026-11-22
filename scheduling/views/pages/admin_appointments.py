"""Section 10: the admin's appointment list, one appointment with the actions of 5.6, and its
cancel step. Status changes and cancel are the use cases of task 08; an admin sees the
appointment and its history, never a clinical note."""

from zoneinfo import ZoneInfo

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import URLPattern, path

from scheduling.domain.audit_labels import audit_label
from scheduling.domain.failure import Failure
from scheduling.domain.staff_actions import StaffAction, staff_actions_for
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, Role
from scheduling.models import Appointment
from scheduling.use_cases.admin_appointments import (
    AdminAppointmentFilters,
    appointment_for_admin,
    filter_clinicians,
    filter_departments,
    list_appointments_for_admin,
)
from scheduling.use_cases.appointment_changes import cancel_appointment, change_status
from scheduling.use_cases.clinician_appointment import appointment_history
from scheduling.views.pages.admin_filters import (
    choice_param,
    day_range,
    page_links,
    page_number,
    uuid_param,
)
from scheduling.views.pages.admin_refusal import admin_refused_page
from scheduling.views.pages.booking_links import clock_label, day_label, path_uuid
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.patient_appointments import reason_error
from scheduling.views.pages.patient_rows import STATUS_BADGES

LIST_PATH = "/admin-console/appointments"
STATUSES = {
    status.value: status.value.replace("_", " ").capitalize() for status in AppointmentStatus
}
SOURCES = {
    source.value: source.value.replace("_", " ").capitalize() for source in AppointmentSource
}
STATUS_BADGE_TEXT = {**STATUS_BADGES, AppointmentStatus.NO_SHOW: ("warning", "No-show")}
BACK_TO_APPOINTMENT = "Back to the appointment"
ACTION_BUTTONS = (
    (StaffAction.CHECK_IN, "Check in"),
    (StaffAction.COMPLETE, "Complete"),
    (StaffAction.NO_SHOW, "No-show"),
)


class AdminAppointmentPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})

    def appointment_or_404(self) -> Appointment:
        found = appointment_for_admin(path_uuid(self, "appointment_id"))
        if found is None:
            raise Http404
        return found


def appointment_path(appointment_id: object) -> str:
    return f"{LIST_PATH}/{appointment_id}"


def when_text(appointment: Appointment) -> str:
    zone_name = appointment.appointment_type.department.hospital.time_zone
    zone = ZoneInfo(zone_name)
    day = day_label(appointment.starts_at.astimezone(zone).date())
    start, end = clock_label(appointment.starts_at, zone), clock_label(appointment.ends_at, zone)
    return f"{day}, {start} to {end} ({zone_name})"


class AppointmentListPage(AdminAppointmentPage):
    template_name = "admin/appointments.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        days = day_range(request)
        department_id = uuid_param(request, "department")
        clinician_id = uuid_param(request, "clinician")
        status = choice_param(request, "status", STATUSES)
        source = choice_param(request, "source", SOURCES)
        filters = AdminAppointmentFilters(
            days.first, days.last, department_id, clinician_id, status, source
        )
        found = list_appointments_for_admin(filters, page_number(request))
        asked = {
            "from": days.first.isoformat() if days.first else "",
            "to": days.last.isoformat() if days.last else "",
            "department": str(department_id or ""),
            "clinician": str(clinician_id or ""),
            "status": status,
            "source": source,
        }
        context = {
            "rows": [_list_row(appointment) for appointment in found.items],
            "total_text": f"{found.total} {'appointment' if found.total == 1 else 'appointments'}",
            "asked": asked,
            "department_options": [("", "Any department")]
            + [(str(row.pk), f"{row.name}, {row.hospital.name}") for row in filter_departments()],
            "clinician_options": [("", "Any clinician")]
            + [(str(row.pk), row.user.full_name) for row in filter_clinicians()],
            "status_options": [("", "Any status"), *STATUSES.items()],
            "source_options": [("", "Any source"), *SOURCES.items()],
            "base_path": LIST_PATH,
            "book_path": f"{LIST_PATH}/new",
            "current": "appointments",
            "page": found.page,
            "page_count": found.page_count,
            **page_links(LIST_PATH, asked, found.page, found.page_count),
        }
        return self.page(request, context)


def _list_row(appointment: Appointment) -> dict[str, str]:
    hospital = appointment.appointment_type.department.hospital
    zone = ZoneInfo(hospital.time_zone)
    local = appointment.starts_at.astimezone(zone)
    return {
        "href": appointment_path(appointment.pk),
        "time": f"{local:%Y-%m-%d %H:%M} ({hospital.time_zone})",
        "patient": appointment.patient.full_name,
        "clinician": appointment.clinician.user.full_name,
        "type_name": appointment.appointment_type.name,
        "status": STATUSES[appointment.status],
        "source": SOURCES[appointment.source],
    }


class AppointmentShowPage(AdminAppointmentPage):
    template_name = "admin/appointment.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        appointment = self.appointment_or_404()
        zone = ZoneInfo(appointment.appointment_type.department.hospital.time_zone)
        status = AppointmentStatus(appointment.status)
        allowed = staff_actions_for(status)
        base = appointment_path(appointment.pk)
        badge_kind, badge_text = STATUS_BADGE_TEXT[status]
        context = {
            "appointment": appointment,
            "when": when_text(appointment),
            "type_name": appointment.appointment_type.name,
            "room": appointment.room.name if appointment.room else "No room",
            "source": SOURCES[appointment.source],
            "badge_kind": badge_kind,
            "badge_text": badge_text,
            "forms": [
                {"action": f"{base}/{action.value}", "label": label}
                for action, label in ACTION_BUTTONS
                if action in allowed
            ],
            "cancel_href": f"{base}/cancel" if StaffAction.CANCEL in allowed else "",
            "reschedule_href": f"{base}/reschedule" if StaffAction.RESCHEDULE in allowed else "",
            "history": [
                {
                    "time": f"{entry.created_at.astimezone(zone):%d %b %Y, %H:%M %Z}",
                    "label": audit_label(entry.action),
                    "actor": entry.actor.full_name if entry.actor else "System",
                }
                for entry in appointment_history(appointment.pk)
            ],
            "time_zone": str(zone),
            "back_path": LIST_PATH,
            "current": "appointments",
        }
        return self.page(request, context)


class StatusActionPage(AdminAppointmentPage):
    http_method_names = ["post"]
    target = AppointmentStatus.CHECKED_IN

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        appointment_id = path_uuid(self, "appointment_id")
        changed = change_status(appointment_id, self.target, self.user)
        if isinstance(changed, Failure):
            back = (appointment_path(appointment_id), BACK_TO_APPOINTMENT)
            return admin_refused_page(request, self.user, changed, back)
        return HttpResponseRedirect(appointment_path(appointment_id), status=303)


class CheckInPage(StatusActionPage):
    target = AppointmentStatus.CHECKED_IN


class CompletePage(StatusActionPage):
    target = AppointmentStatus.COMPLETED


class NoShowPage(StatusActionPage):
    target = AppointmentStatus.NO_SHOW


class CancelPage(AdminAppointmentPage):
    template_name = "admin/appointment_cancel.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        return self._form(request, self.appointment_or_404(), "", "")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        appointment = self.appointment_or_404()
        reason = request.POST.get("reason", "").strip()
        error = reason_error(reason)
        if error:
            return self._form(request, appointment, reason, error, 422)
        cancelled = cancel_appointment(appointment.pk, reason, self.user)
        back = (appointment_path(appointment.pk), BACK_TO_APPOINTMENT)
        if isinstance(cancelled, Failure):
            return admin_refused_page(request, self.user, cancelled, back)
        return HttpResponseRedirect(appointment_path(appointment.pk), status=303)

    def _form(
        self,
        request: HttpRequest,
        appointment: Appointment,
        reason: str,
        error: str,
        status: int = 200,
    ) -> HttpResponse:
        context = {
            "patient": appointment.patient.full_name,
            "when": when_text(appointment),
            "type_name": appointment.appointment_type.name,
            "reason": reason,
            "error": error,
            "cancel_errors": [{"target": "id_reason", "message": error}],
            "action": request.path,
            "back_path": appointment_path(appointment.pk),
            "current": "appointments",
        }
        return self.page(request, context, status)


def admin_appointment_routes() -> list[URLPattern]:
    one = "admin-console/appointments/<uuid:appointment_id>"
    return [
        path("admin-console/appointments", AppointmentListPage.as_view()),
        path(one, AppointmentShowPage.as_view()),
        path(f"{one}/check-in", CheckInPage.as_view()),
        path(f"{one}/complete", CompletePage.as_view()),
        path(f"{one}/no-show", NoShowPage.as_view()),
        path(f"{one}/cancel", CancelPage.as_view()),
    ]
