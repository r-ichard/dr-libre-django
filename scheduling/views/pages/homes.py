"""Section 12: the three role homes, each behind its access rule."""

from scheduling.domain.sign_in_rules import Home
from scheduling.domain.vocabulary import Role
from scheduling.views.pages.page_view import PageView

HOME_PATHS = {
    Home.PATIENT_PORTAL: "/patient/",
    Home.CLINICIAN_WORKSPACE: "/clinician/",
    Home.ADMIN_CONSOLE: "/admin-console/",
}


class PatientPortal(PageView):
    template_name = "homes/patient.html"
    allowed_roles = frozenset({Role.PATIENT})


class ClinicianWorkspace(PageView):
    template_name = "homes/clinician.html"
    allowed_roles = frozenset({Role.CLINICIAN})


class AdminConsole(PageView):
    template_name = "homes/admin.html"
    allowed_roles = frozenset({Role.ADMIN})
