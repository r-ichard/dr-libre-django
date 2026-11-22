"""Task 26b item 9, section 11: every log line of one booking, one sign-in by link, one admin user
edit and one FHIR patient read, read as the formatter writes it. No personal value or secret in
any of them."""

from __future__ import annotations

import io
import json
import logging
import re
import secrets
from collections.abc import Iterator
from datetime import date

import pytest
from django.core import mail

from scheduling.models import User
from scheduling.models.builders import STARTS_AT, make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.fhir_test_support import NOW, get, token_of
from scheduling.views.json_logging import JsonFormatter
from scheduling.views.pages.admin_support import admin_client, admin_post

pytestmark = pytest.mark.django_db

CONSOLE = "/admin-console"
BOOKING_EMAIL = "planted.booker@example.test"
BOOKING_NAME = "Vera Plantedbooker"
BOOKING_PHONE = "+49 30 7770042"
BOOKING_BIRTH_DATE = "1985-03-14"
LINK_EMAIL = "planted.linker@example.test"
LINK_TOKEN = "planted-link-token-0123456789abcdefghijk"  # noqa: S105
EDIT_EMAIL = "planted.edited@example.test"
EDIT_NAME = "Edda Plantededit"
PATIENT_NAME = "Pia Plantedpatient"
PATIENT_PHONE = "+49 40 5550199"
PATIENT_BIRTH_DATE = date(1979, 11, 2)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_PATTERN = re.compile(r"\d[\d ()-]{5,}\d")
GENERATED_FIELDS = ("time", "correlation_id", "duration_ms")
BIRTH_DATE_PATTERN = re.compile(r"\b(19|20)\d\d-\d\d-\d\d\b")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.fixture
def written() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    previous = root.level
    root.setLevel(logging.DEBUG)
    yield stream
    root.removeHandler(handler)
    root.setLevel(previous)


def _book() -> list[str]:
    clinic = make_clinic()
    client = browser_api_client()
    body = {
        "appointment_type_id": str(clinic.appointment_type.pk),
        "clinician_id": str(clinic.clinician.pk),
        "starts_at": STARTS_AT.isoformat(),
        "full_name": BOOKING_NAME,
        "date_of_birth": BOOKING_BIRTH_DATE,
        "email": BOOKING_EMAIL,
        "phone": BOOKING_PHONE,
        "reason": "Sore knee",
        "terms_accepted": True,
    }
    holds = "/api/v1/booking/holds"
    hold_id = client.post(holds, body, content_type="application/json").json()["id"]
    found = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert found is not None
    verified = client.post(
        f"{holds}/{hold_id}/verify", {"code": found.group(1)}, content_type="application/json"
    )
    assert verified.status_code == 201
    return [found.group(1)]


def _sign_in_by_link(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    make("User", email=LINK_EMAIL)
    client = browser_api_client()
    with monkeypatch.context() as planting:
        planting.setattr(secrets, "token_urlsafe", lambda _size=None: LINK_TOKEN)
        asked = client.post(
            "/api/v1/auth/link", {"email": LINK_EMAIL}, content_type="application/json"
        )
    used = client.post(
        "/api/v1/auth/link/verify", {"token": LINK_TOKEN}, content_type="application/json"
    )
    assert (asked.status_code, used.status_code) == (202, 200)
    return [LINK_TOKEN]


def _edit_user() -> list[str]:
    target = make_user(role="PATIENT")
    form = {
        "full_name": EDIT_NAME,
        "email": EDIT_EMAIL,
        "role": "PATIENT",
        "is_active": "on",
        "version": str(target.version),
    }
    response = admin_post(admin_client(), f"{CONSOLE}/users/{target.pk}/edit", form)
    assert response.status_code == 303
    assert User.objects.get(pk=target.pk).email == EDIT_EMAIL
    return []


def _read_patient() -> list[str]:
    patient = make_user(
        role="PATIENT",
        full_name=PATIENT_NAME,
        phone=PATIENT_PHONE,
        date_of_birth=PATIENT_BIRTH_DATE,
    )
    token = token_of(patient)
    assert get(f"/fhir/Patient/{patient.pk}", token).status_code == 200
    return [token]


def returns_no_personal_value_in_any_log_line_when_the_four_flows_run(
    written: io.StringIO, monkeypatch: pytest.MonkeyPatch, settings: object
) -> None:
    secrets_planted = [
        *_book(),
        *_sign_in_by_link(monkeypatch),
        *_edit_user(),
        *_read_patient(),
    ]
    planted = [
        BOOKING_EMAIL, BOOKING_NAME, BOOKING_PHONE, BOOKING_BIRTH_DATE, LINK_EMAIL, EDIT_EMAIL,
        EDIT_NAME, PATIENT_NAME, PATIENT_PHONE, PATIENT_BIRTH_DATE.isoformat(), *secrets_planted,
    ]  # fmt: skip
    lines = written.getvalue().splitlines()

    assert lines, "no log line captured: the handler is not plugged in"
    assert sum('"method"' in line for line in lines) >= 4
    for line in lines:
        assert not [value for value in planted if value in line], line
        user_fields = {
            key: value for key, value in json.loads(line).items() if key not in GENERATED_FIELDS
        }
        for pattern in (EMAIL_PATTERN, PHONE_PATTERN, BIRTH_DATE_PATTERN):
            assert pattern.search(json.dumps(user_fields)) is None, line
