"""Section 12: the three role homes, each behind its access rule."""

from django.http import HttpRequest, HttpResponse

from scheduling.domain.sign_in_rules import Home
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.notification_inbox import unread_count
from scheduling.use_cases.patient_appointments import upcoming_appointments
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.patient_rows import appointment_row

HOME_PATHS = {
    Home.PATIENT_PORTAL: "/patient/",
    Home.CLINICIAN_WORKSPACE: "/clinician/",
    Home.ADMIN_CONSOLE: "/admin-console/",
}


class PatientPortal(PageView):
    template_name = "homes/patient.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        now = current_request_context().now
        soonest = upcoming_appointments(self.user, now)[:1]
        context = {
            "next_row": appointment_row(soonest[0], now) if soonest else None,
            "unread_count": unread_count(self.user),
        }
        return self.page(request, context)


class ClinicianWorkspace(PageView):
    template_name = "homes/clinician.html"
    allowed_roles = frozenset({Role.CLINICIAN})


class AdminConsole(PageView):
    template_name = "homes/admin.html"
    allowed_roles = frozenset({Role.ADMIN})
