"""Section 14: the three hold endpoints. Public, strict, the same answer for every kind of
address, and rate limited with a code of its own."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.test import Client

from scheduling.models import Appointment, BookingHold, Session, User
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

HOLDS = "/api/v1/booking/holds"
COOKIE = "drlibre_session"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
EMAIL = "visitor.api@example.test"
HOLD_KEYS = {"id", "appointment_type_id", "clinician_id", "starts_at", "ends_at", "expires_at"}


class MailServerDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise ConnectionRefusedError("mail server down")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _body(clinic: Clinic, **overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": STARTS_AT.isoformat(),
        "full_name": "Vera Visitor",
        "date_of_birth": "1985-03-14",
        "email": EMAIL,
        "phone": "+49 30 777",
        "reason": "Sore knee",
        "terms_accepted": True,
    }
    return {**fields, **overrides}


def _post(
    path: str, body: Mapping[str, object], client: Client | None = None
) -> _MonkeyPatchedWSGIResponse:
    return (client or browser_api_client()).post(path, body, content_type="application/json")


def _code() -> str:
    found = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert found is not None
    return found.group(1)


def returns_201_and_hold_body_only_when_visitor_holds_a_slot() -> None:
    clinic = make_clinic()

    response = _post(HOLDS, _body(clinic))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == HOLD_KEYS
    assert body["expires_at"] == "2030-01-07T06:10:00Z"
    assert body["clinician_id"] == str(clinic.clinician.pk)
    assert len(mail.outbox) == 1


def returns_400_invalid_input_when_body_has_an_unknown_field() -> None:
    clinic = make_clinic()

    response = _post(HOLDS, _body(clinic, patient_id=str(clinic.patient.pk)))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
    assert BookingHold.objects.count() == 0


def returns_400_invalid_input_when_terms_are_not_accepted_or_missing() -> None:
    clinic = make_clinic()
    missing = {key: value for key, value in _body(clinic).items() if key != "terms_accepted"}

    refused = _post(HOLDS, _body(clinic, terms_accepted=False))
    absent = _post(HOLDS, missing)

    assert (refused.status_code, absent.status_code) == (400, 400)
    assert BookingHold.objects.count() == 0


def returns_404_when_hold_id_is_unknown_on_resend_and_verify() -> None:
    unknown = "00000000-0000-4000-8000-000000000000"

    resend = _post(f"{HOLDS}/{unknown}/resend", {})
    verify = _post(f"{HOLDS}/{unknown}/verify", {"code": "123456"})

    assert (resend.status_code, verify.status_code) == (404, 404)
    assert resend.json()["error"]["code"] == "not_found"


def returns_404_when_holds_are_read_with_get() -> None:
    assert browser_api_client().get(HOLDS).status_code == 404


def returns_200_and_new_code_when_code_is_resent() -> None:
    clinic = make_clinic()
    hold_id = _post(HOLDS, _body(clinic)).json()["id"]

    response = _post(f"{HOLDS}/{hold_id}/resend", {})

    assert response.status_code == 200
    assert len(mail.outbox) == 2


def returns_201_appointment_and_session_cookie_when_code_is_right() -> None:
    clinic = make_clinic()
    hold_id = _post(HOLDS, _body(clinic)).json()["id"]

    response = _post(f"{HOLDS}/{hold_id}/verify", {"code": _code()})

    assert response.status_code == 201
    assert response.json()["starts_at"] == "2030-01-07T10:00:00Z"
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    session = Session.objects.get()
    assert session.expires_at == NOW + timedelta(hours=24)
    assert Appointment.objects.get().patient.email == EMAIL


def returns_400_invalid_input_on_field_code_when_code_is_wrong() -> None:
    clinic = make_clinic()
    hold_id = _post(HOLDS, _body(clinic)).json()["id"]
    wrong = "000000" if _code() != "000000" else "111111"

    response = _post(f"{HOLDS}/{hold_id}/verify", {"code": wrong})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["details"] == {"fields": [{"field": "code", "message": "The code is not valid."}]}
    assert COOKIE not in response.cookies


def returns_400_when_code_is_not_six_digits() -> None:
    clinic = make_clinic()
    hold_id = _post(HOLDS, _body(clinic)).json()["id"]

    response = _post(f"{HOLDS}/{hold_id}/verify", {"code": "12"})

    assert response.status_code == 400


def returns_403_generic_when_the_right_code_is_sent_for_a_staff_address() -> None:
    clinic = make_clinic()
    make("User", email=EMAIL, role="ADMIN")
    hold_id = _post(HOLDS, _body(clinic)).json()["id"]

    response = _post(f"{HOLDS}/{hold_id}/verify", {"code": _code()})

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "You are not allowed to do this."
    assert COOKIE not in response.cookies
    assert Appointment.objects.count() == 0


def returns_same_status_and_body_shape_when_address_is_new_patient_or_staff() -> None:
    make("User", email="known.patient@example.test")
    make("User", email="some.admin@example.test", role="ADMIN")
    answers = []
    for email in (EMAIL, "known.patient@example.test", "some.admin@example.test"):
        answers.append(_post(HOLDS, _body(make_clinic(), email=email)))

    assert {answer.status_code for answer in answers} == {201}
    assert {frozenset(answer.json()) for answer in answers} == {frozenset(HOLD_KEYS)}
    assert User.objects.filter(role="PATIENT").count() >= 2


def returns_429_rate_limited_with_wire_shape_when_sixth_hold_of_an_email_is_asked() -> None:
    clinic = make_clinic()
    for _ in range(5):
        assert _post(HOLDS, _body(clinic)).status_code == 201

    response = _post(HOLDS, _body(clinic))

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["message"] == "Too many requests."
    assert error["details"] == {}
    assert error["correlation_id"]


def returns_503_mail_unavailable_and_no_hold_when_mail_server_is_down(settings: object) -> None:
    clinic = make_clinic()
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.MailServerDownBackend", "OPTIONS": {}}
    }

    response = browser_api_client(raise_request_exception=False).post(
        HOLDS, _body(clinic), content_type="application/json"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "mail_unavailable"
    assert (
        response.json()["error"]["message"]
        == "We could not send the email. Try again in a few minutes."
    )
    assert EMAIL not in response.content.decode()
    assert BookingHold.objects.count() == 0
