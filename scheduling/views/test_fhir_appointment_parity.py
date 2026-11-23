"""Section 15.6: a booking, a reschedule and a cancellation over FHIR leave what the same
change on the screens leaves: audit entry, notification, email, portal row. Two identical
clinics, one changed by a screen, one by FHIR; the results are compared."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client

from scheduling.models import Appointment, AuditLogEntry, Notification
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.background_mail import wait_until_idle
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, send, token_of
from scheduling.views.pages.booking_pages_support import details_path, signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

IDENTIFIER = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LATER = STARTS_AT + timedelta(days=7)
NEW_START = STARTS_AT + timedelta(days=14)
FIRST_ADDRESS = "/patient/appointments"
STAMP = "%Y-%m-%dT%H:%M:%SZ"

type Capture = Callable[[Callable[[], None]], None]


@dataclass(frozen=True)
class Trace:
    audit: list[tuple[str, str]]
    notifications: list[tuple[str, str, str]]
    mails: list[tuple[str, str]]
    portal: list[str]


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _blind(text: str, clinic: Clinic) -> str:
    """The text with each name that belongs to one of the two worlds replaced by its role."""
    for role, value in {
        "patient-email": clinic.patient.email,
        "patient-name": clinic.patient.full_name,
        "type": clinic.appointment_type.name,
        "department": clinic.department.name,
        "hospital": clinic.department.hospital.name,
        "clinician": clinic.clinician.user.full_name,
    }.items():
        text = text.replace(value, f"<{role}>")
    return IDENTIFIER.sub("<id>", text)


def _trace(clinic: Clinic, portal_client: Client, after: int) -> Trace:
    wait_until_idle()
    entries = AuditLogEntry.objects.order_by("created_at", "pk")[after:]
    portal = portal_client.get(FIRST_ADDRESS).content.decode()
    rows = re.findall(r"<(?:li|tr)[^>]*>.*?</(?:li|tr)>", portal, flags=re.S)
    return Trace(
        audit=[(e.action, _blind(json.dumps(e.metadata, sort_keys=True), clinic)) for e in entries],
        notifications=[
            (n.kind, str(n.title), _blind(str(n.body), clinic))
            for n in Notification.objects.filter(recipient=clinic.patient).order_by("pk")
        ],
        mails=[(str(m.subject), _blind(str(m.body), clinic)) for m in mail.outbox],
        portal=[_blind(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)), clinic) for row in rows],
    )


def _booked(clinic: Clinic, starts_at: object = LATER) -> Appointment:
    row = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),  # type: ignore[operator]
    )
    assert isinstance(row, Appointment)
    return row


def _both(
    prepare: Callable[[Clinic], str],
    on_screen: Callable[[Clinic, Client, str], None],
    on_fhir: Callable[[Clinic, str, str], None],
    capture: Capture,
) -> tuple[Trace, Trace]:
    return (
        _trace_of(prepare, on_screen, None, capture),
        _trace_of(prepare, None, on_fhir, capture),
    )


def _trace_of(
    prepare: Callable[[Clinic], str],
    on_screen: Callable[[Clinic, Client, str], None] | None,
    on_fhir: Callable[[Clinic, str, str], None] | None,
    capture: Capture,
) -> Trace:
    clinic = make_clinic()
    key = prepare(clinic)
    client, token = signed_in_patient(clinic.patient), token_of(clinic.patient)
    mail.outbox.clear()
    before = AuditLogEntry.objects.count()
    Notification.objects.filter(recipient=clinic.patient).delete()
    if on_screen is not None:
        capture(lambda: on_screen(clinic, client, key))
    if on_fhir is not None:
        capture(lambda: on_fhir(clinic, token, key))
    return _trace(clinic, client, before)


@pytest.fixture
def capture(django_capture_on_commit_callbacks: Callable[..., object]) -> Capture:
    def run(action: Callable[[], None]) -> None:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[attr-defined]
            action()

    return run


def returns_the_same_trace_when_a_booking_is_made_over_fhir_and_on_the_screen(
    capture: Capture,
) -> None:
    def on_screen(clinic: Clinic, client: Client, _key: str) -> None:
        form = {"reason": "Sore knee", "terms_accepted": "on"}
        assert browser_post(client, details_path(clinic), form).status_code == 303

    def on_fhir(clinic: Clinic, token: str, _key: str) -> None:
        body = {
            "resourceType": "Appointment",
            "status": "proposed",
            "start": STARTS_AT.strftime(STAMP),
            "reasonCode": [{"text": "Sore knee"}],
            "serviceType": [{"coding": [{"code": str(clinic.appointment_type.pk)}]}],
            "participant": [
                {"actor": {"reference": f"Patient/{clinic.patient.pk}"}, "status": "accepted"},
                {
                    "actor": {"reference": f"Practitioner/{clinic.clinician.user_id}"},
                    "status": "accepted",
                },
            ],
        }
        assert send("post", "/fhir/Appointment", body, token).status_code == 201

    screen, fhir = _both(lambda _clinic: "", on_screen, on_fhir, capture)

    assert screen.audit and screen.notifications and screen.mails and screen.portal
    assert fhir == screen


def returns_the_same_trace_when_a_reschedule_is_made_over_fhir_and_on_the_screen(
    capture: Capture,
) -> None:
    def prepare(clinic: Clinic) -> str:
        return str(_booked(clinic).pk)

    def on_screen(_clinic: Clinic, client: Client, key: str) -> None:
        stamp = NEW_START.strftime(STAMP)
        answer = browser_post(
            client, f"{FIRST_ADDRESS}/{key}/reschedule/review?starts_at={stamp}", {}
        )
        assert answer.status_code == 303

    def on_fhir(_clinic: Clinic, token: str, key: str) -> None:
        body = get(f"/fhir/Appointment/{key}", token).json()
        body["start"] = NEW_START.strftime(STAMP)
        body["end"] = (NEW_START + timedelta(minutes=30)).strftime(STAMP)
        assert send("put", f"/fhir/Appointment/{key}", body, token).status_code == 200

    screen, fhir = _both(prepare, on_screen, on_fhir, capture)

    assert screen.audit and screen.notifications and screen.mails and screen.portal
    assert fhir == screen


def returns_the_same_trace_when_a_cancellation_is_made_over_fhir_and_on_the_screen(
    capture: Capture,
) -> None:
    def prepare(clinic: Clinic) -> str:
        return str(_booked(clinic).pk)

    def on_screen(_clinic: Clinic, client: Client, key: str) -> None:
        answer = browser_post(client, f"{FIRST_ADDRESS}/{key}/cancel", {"reason": "Cannot come"})
        assert answer.status_code == 303

    def on_fhir(_clinic: Clinic, token: str, key: str) -> None:
        body = get(f"/fhir/Appointment/{key}", token).json()
        body["status"] = "cancelled"
        body["cancelationReason"] = {"text": "Cannot come"}
        assert send("put", f"/fhir/Appointment/{key}", body, token).status_code == 200

    screen, fhir = _both(prepare, on_screen, on_fhir, capture)

    assert screen.audit and screen.notifications and screen.mails and screen.portal
    assert fhir == screen
