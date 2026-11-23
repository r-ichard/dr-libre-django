"""Task 26b3 item 1: who may call each /api/v1 route, and the answer each caller gets (visitor,
patient, clinician, admin). Data only: nothing reads it at runtime. Own record only; another user's
record is checked by the walk of item 3."""

from dataclasses import dataclass

ANY_METHOD = "ANY"


@dataclass(frozen=True)
class AccessRow:
    method: str
    route: str
    visitor: int
    patient: int
    clinician: int
    admin: int
    basis: str


# Cells are HTTP statuses; basis cites drlibre-specs.md. Rows follow URL-configuration order.
# Cells assume a valid body and the caller's own credentials. Visitor gets 401 on signed-in routes.
API_ACCESS_ROWS: tuple[AccessRow, ...] = (
    AccessRow("GET", "api/v1/health", 200, 200, 200, 200, "§14 anyone; HealthView AllowAny"),
    AccessRow(
        "POST",
        "api/v1/auth/login",
        401,
        200,
        200,
        200,
        "§12.1; wrong credentials are unauthenticated (sign_in.py:58)",
    ),
    AccessRow("POST", "api/v1/auth/logout", 204, 204, 204, 204, "§14 anyone"),
    AccessRow("POST", "api/v1/auth/link", 202, 202, 202, 202, "§14 anyone; 202 for every address"),
    AccessRow(
        "POST",
        "api/v1/auth/link/verify",
        200,
        200,
        400,
        400,
        "§7.3, §12.1; a clinician or admin has no link: invalid_input (sign_in_link.py:31)",
    ),
    AccessRow("GET", "api/v1/slots", 200, 200, 200, 200, "§12.3, §14 public"),
    AccessRow("GET", "api/v1/search/providers", 200, 200, 200, 200, "§14 anyone"),
    AccessRow("GET", "api/v1/search/hospitals", 200, 200, 200, 200, "§14 anyone"),
    AccessRow("GET", "api/v1/search/specialties", 200, 200, 200, 200, "§14 anyone"),
    AccessRow(
        "GET",
        "api/v1/hospitals/<uuid:hospital_id>",
        200,
        200,
        200,
        200,
        "§14 anyone; active record, §4 not_found when inactive",
    ),
    AccessRow(
        "GET",
        "api/v1/providers/<uuid:provider_id>",
        200,
        200,
        200,
        200,
        "§14 anyone; active record, §4 not_found when inactive",
    ),
    AccessRow(
        "GET",
        "api/v1/specialties/<uuid:specialty_id>",
        200,
        200,
        200,
        200,
        "§14 anyone; active record, §4 not_found when inactive",
    ),
    AccessRow("POST", "api/v1/booking/holds", 201, 201, 201, 201, "§14 anyone"),
    AccessRow(
        "POST",
        "api/v1/booking/holds/<uuid:hold_id>/resend",
        200,
        200,
        200,
        200,
        "§14 anyone; a hold has no owner",
    ),
    AccessRow(
        "POST",
        "api/v1/booking/holds/<uuid:hold_id>/verify",
        201,
        201,
        201,
        201,
        "§7.1, §14 anyone; opens a session",
    ),
    AccessRow("GET", "api/v1/appointments", 401, 200, 200, 200, "§14 signed in; list is scoped"),
    AccessRow(
        "POST",
        "api/v1/appointments",
        401,
        201,
        201,
        201,
        "§5.4: patient for self, clinician into own calendar, admin for any",
    ),
    AccessRow(
        "POST",
        "api/v1/appointments/<uuid:appointment_id>/cancel",
        401,
        200,
        200,
        200,
        "§14 patient, clinician, admin; own appointment",
    ),
    AccessRow(
        "POST",
        "api/v1/appointments/<uuid:appointment_id>/reschedule",
        401,
        200,
        200,
        200,
        "§14 patient, clinician, admin; own appointment",
    ),
    AccessRow(
        "POST",
        "api/v1/appointments/<uuid:appointment_id>/check-in",
        401,
        403,
        200,
        200,
        "§14 clinician, admin; roles(CLINICIAN, ADMIN) refuses a patient",
    ),
    AccessRow(
        "POST",
        "api/v1/appointments/<uuid:appointment_id>/complete",
        401,
        403,
        200,
        200,
        "§14 clinician, admin; roles(CLINICIAN, ADMIN) refuses a patient",
    ),
    AccessRow(
        "POST",
        "api/v1/appointments/<uuid:appointment_id>/no-show",
        401,
        403,
        200,
        200,
        "§14 clinician, admin; roles(CLINICIAN, ADMIN) refuses a patient",
    ),
    AccessRow(
        "POST",
        "api/v1/waitlist",
        401,
        201,
        403,
        201,
        "§5.8 join: patient for self, admin names a patient (waitlist_rules.py:94)",
    ),
    AccessRow(
        "POST",
        "api/v1/waitlist/<uuid:entry_id>/accept",
        401,
        200,
        403,
        200,
        "§5.8 patient for own entry, or admin",
    ),
    AccessRow(
        "POST",
        "api/v1/waitlist/<uuid:entry_id>/offer",
        401,
        403,
        403,
        200,
        "§5.8 manual offer, admin; not in §14 (waitlist.py:106)",
    ),
    AccessRow("POST", "api/v1/jobs/reminders", 401, 403, 403, 200, "§14 admin"),
    AccessRow(
        ANY_METHOD,
        "^api/v1/",
        404,
        404,
        404,
        404,
        "§4 unknown or undeclared route under the API prefix: not_found (failure_response.py:95)",
    ),
)
