"""Section 12: the home a signed-in user lands on."""

from enum import StrEnum

from scheduling.models.people import Role


class Home(StrEnum):
    PATIENT_PORTAL = "patient_portal"
    CLINICIAN_WORKSPACE = "clinician_workspace"
    ADMIN_CONSOLE = "admin_console"


HOME_BY_ROLE = {
    Role.PATIENT: Home.PATIENT_PORTAL,
    Role.CLINICIAN: Home.CLINICIAN_WORKSPACE,
    Role.ADMIN: Home.ADMIN_CONSOLE,
}


def home_for(role: Role) -> Home:
    return HOME_BY_ROLE[role]
