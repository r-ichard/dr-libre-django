"""The clinician's appointment page: details, history, the clinical note. Status changes,
cancel and reschedule go through the task 08 use cases; the note through its own use case."""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.audit_labels import audit_label
from scheduling.domain.clinical_note_rules import CLINICAL_NOTE_MAXIMUM
from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.staff_actions import StaffAction, staff_actions_for
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.use_cases.appointment_changes import cancel_appointment
from scheduling.use_cases.clinical_notes import read_clinical_note, save_clinical_note
from scheduling.use_cases.clinician_appointment import appointment_history
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.booking_links import clock_label, day_label
from scheduling.views.pages.clinician_support import (
    CLINICIAN_BADGES,
    TODAY_PATH,
    ClinicianPage,
    appointment_path,
)
from scheduling.views.pages.patient_appointments import reason_error
from scheduling.views.pages.patient_refusal import change_refused_page

NOTICES = {"note-saved": "The note is saved."}


def age_in_years(born: date | None, now: datetime) -> int | None:
    if born is None:
        return None
    return now.year - born.year - ((now.month, now.day) < (born.month, born.day))


def _details(appointment: Appointment) -> dict[str, object]:
    hospital = appointment.appointment_type.department.hospital
    zone = ZoneInfo(hospital.time_zone)
    now = current_request_context().now
    status = AppointmentStatus(appointment.status)
    badge_kind, badge_text = CLINICIAN_BADGES[status]
    allowed = staff_actions_for(status)
    base = appointment_path(appointment.pk)
    patient = appointment.patient
    return {
        "patient": patient.full_name,
        "phone": patient.phone,
        "age": age_in_years(patient.date_of_birth, now),
        "day": day_label(appointment.starts_at.astimezone(zone).date()),
        "time": (
            f"{clock_label(appointment.starts_at, zone)} to "
            f"{clock_label(appointment.ends_at, zone)}"
        ),
        "time_zone": hospital.time_zone,
        "type_name": appointment.appointment_type.name,
        "room": appointment.room.name if appointment.room else "",
        "reason": appointment.patient_reason,
        "cancelled_reason": appointment.cancellation_reason,
        "badge_kind": badge_kind,
        "badge_text": badge_text,
        "forms": [
            {"action": f"{base}/{action.value}", "label": label}
            for action, label in (
                (StaffAction.CHECK_IN, "Check in"),
                (StaffAction.COMPLETE, "Complete"),
                (StaffAction.NO_SHOW, "No-show"),
            )
            if action in allowed
        ],
        "cancel_href": f"{base}/cancel" if StaffAction.CANCEL in allowed else "",
        "reschedule_href": f"{base}/reschedule" if StaffAction.RESCHEDULE in allowed else "",
        "notes_action": f"{base}/notes",
        "note_maximum": CLINICAL_NOTE_MAXIMUM,
        "history": _history(appointment, zone),
    }


def _history(appointment: Appointment, zone: ZoneInfo) -> list[dict[str, str]]:
    return [
        {
            "time": f"{entry.created_at.astimezone(zone):%d %b %Y, %H:%M %Z}",
            "label": audit_label(entry.action),
            "actor": entry.actor.full_name if entry.actor else "System",
        }
        for entry in appointment_history(appointment.pk)
    ]


class AppointmentPage(ClinicianPage):
    template_name = "clinician/appointment.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        notice = NOTICES.get(request.GET.get("notice", ""), "")
        return self.render_details(request, found, notice=notice)

    def render_details(
        self,
        request: HttpRequest,
        appointment: Appointment,
        *,
        notice: str = "",
        note: str | None = None,
        note_error: str = "",
        status: int = 200,
    ) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        if note is None:
            stored = read_clinical_note(UUID(str(appointment.pk)), self.user)
            if isinstance(stored, Failure):
                return self.refusal_of(request, stored)
            note = stored.value
        context = {
            **_details(appointment),
            "notice": notice,
            "note": note,
            "note_error": note_error,
            "note_errors": [{"target": "id_clinical_notes", "message": note_error}],
            "today_path": TODAY_PATH,
        }
        return self.page(request, context, status)


class NotesPage(AppointmentPage):
    form_page = "/clinician/appointments/{appointment_id}"
    http_method_names = ["post"]

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        text = request.POST.get("clinical_notes", "")
        saved = save_clinical_note(UUID(str(found.pk)), text, self.user)
        if isinstance(saved, Failure):
            if saved.code != FailureCode.INVALID_INPUT:
                return self.refusal_of(request, saved)
            return self.render_details(
                request, found, note=text, note_error=saved.field_messages[0].message, status=422
            )
        return HttpResponseRedirect(f"{appointment_path(found.pk)}?notice=note-saved", status=303)


class CancelPage(ClinicianPage):
    template_name = "clinician/cancel.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        return self._form(request, found, "", "")

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        found = self.appointment_or_refusal(request)
        if isinstance(found, HttpResponse):
            return found
        reason = request.POST.get("reason", "").strip()
        error = reason_error(reason)
        if error:
            return self._form(request, found, reason, error, 422)
        cancelled = cancel_appointment(UUID(str(found.pk)), reason, self.user)
        if isinstance(cancelled, Failure):
            back = (appointment_path(found.pk), "Back to the appointment")
            return change_refused_page(request, cancelled, self.user, back_action=back)
        return HttpResponseRedirect(appointment_path(found.pk), status=303)

    def _form(
        self, request: HttpRequest, found: Appointment, reason: str, error: str, status: int = 200
    ) -> HttpResponse:
        details = _details(found)
        context = {
            "patient": details["patient"],
            "day": details["day"],
            "time": details["time"],
            "type_name": details["type_name"],
            "reason": reason,
            "error": error,
            "cancel_errors": [{"target": "id_reason", "message": error}],
            "action": request.path,
            "back_path": appointment_path(found.pk),
        }
        return self.page(request, context, status)
