"""Sections 12.3 and 14: the answer each caller gets to a page that needs no session, and to the
debug-only style page. The types here are shared by the other test_page_access_rows*.py files."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Answer(StrEnum):
    OK = "ok"
    SIGN_IN = "sign-in"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not-found"


OK = Answer.OK
SIGN_IN = Answer.SIGN_IN
FORBIDDEN = Answer.FORBIDDEN


@dataclass(frozen=True)
class Row:
    route: str
    visitor: Answer
    patient: Answer
    clinician: Answer
    admin: Answer
    names_record: bool = False
    debug_only: bool = False


NO_SESSION_ROWS: tuple[Row, ...] = (
    Row("", OK, OK, OK, OK),
    Row("favicon.ico", OK, OK, OK, OK),
    Row("providers/<uuid:provider_id>", OK, OK, OK, OK, names_record=True),
    Row("hospitals/<uuid:hospital_id>", OK, OK, OK, OK, names_record=True),
    Row("specialties/<uuid:specialty_id>", OK, OK, OK, OK, names_record=True),
    Row("terms", OK, OK, OK, OK),
    Row("privacy", OK, OK, OK, OK),
    Row("sign-in", OK, OK, OK, OK),
    Row("sign-in/email-link", OK, OK, OK, OK),
    Row("sign-in/check-email", OK, OK, OK, OK),
    Row("sign-in/link", OK, OK, OK, OK),
    Row("sign-out", OK, OK, OK, OK),
    Row("book/holds/<uuid:hold_id>/code", OK, OK, OK, OK, names_record=True),
    Row("book/holds/<uuid:hold_id>/resend", OK, OK, OK, OK, names_record=True),
    Row("book", OK, OK, OK, OK),
    Row("book/<uuid:appointment_type_id>/provider", OK, OK, OK, OK, names_record=True),
    Row("book/<uuid:appointment_type_id>", OK, OK, OK, OK, names_record=True),
    Row("book/<uuid:appointment_type_id>/details", OK, OK, OK, OK, names_record=True),
)

STYLE_ROWS: tuple[Row, ...] = (Row("style", OK, OK, OK, OK, debug_only=True),)

Caller = Literal["visitor", "patient", "clinician", "admin"]

# (route, caller) -> (answer in the table, answer the product gives). Each entry is a question
# for the owner, listed under "For the owner" in the review.
KNOWN_DIFFERENCES: dict[tuple[str, Caller], tuple[Answer, str]] = {
    ("favicon.ico", "visitor"): (Answer.OK, "302 /static/favicon.svg"),
    ("favicon.ico", "patient"): (Answer.OK, "302 /static/favicon.svg"),
    ("favicon.ico", "clinician"): (Answer.OK, "302 /static/favicon.svg"),
    ("favicon.ico", "admin"): (Answer.OK, "302 /static/favicon.svg"),
    ("sign-in", "patient"): (Answer.OK, "302 /patient/"),
    ("sign-in", "clinician"): (Answer.OK, "302 /clinician/"),
    ("sign-in", "admin"): (Answer.OK, "302 /admin-console/"),
    ("admin-console/appointments/new/service", "admin"): (
        Answer.OK,
        "302 /admin-console/appointments/new",
    ),
    ("book/<uuid:appointment_type_id>/details", "clinician"): (Answer.OK, Answer.FORBIDDEN),
    ("book/<uuid:appointment_type_id>/details", "admin"): (Answer.OK, Answer.FORBIDDEN),
    ("admin-console/appointments/new/<uuid:appointment_type_id>/provider", "admin"): (
        Answer.OK,
        "302 /admin-console/appointments/new",
    ),
    ("admin-console/appointments/new/<uuid:appointment_type_id>/times", "admin"): (
        Answer.OK,
        "302 /admin-console/appointments/new",
    ),
    ("admin-console/appointments/new/<uuid:appointment_type_id>/review", "admin"): (
        Answer.OK,
        "302 /admin-console/appointments/new",
    ),
}
