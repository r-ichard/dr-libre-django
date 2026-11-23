"""Sections 12.3 and 14: the answer each caller gets to a page that needs no session, and to the
debug-only style page. The types here are shared by the other test_page_access_rows*.py files."""

from dataclasses import dataclass
from enum import StrEnum


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
