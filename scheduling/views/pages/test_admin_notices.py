"""Task 21, item 17: every admin action that changes something answers with a notice that says
what was done and for whom, shown once. The guard lists the POST routes of the console by view
class, so a new action without a notice fails here."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import signing
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.models import Appointment, Specialty, User
from scheduling.models.builders import make, make_clinic, make_user
from scheduling.use_cases.test_waitlist_support import (
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.views import clock
from scheduling.views.pages.admin_notices import ADMIN_NOTICE_COOKIE, NOTICE_SALT
from scheduling.views.pages.admin_support import admin_client, admin_post

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
LIST = "/admin-console/appointments"
WAITLIST = "/admin-console/waitlist"
PATIENT_NAME = "Ana Silva"
Action = Callable[[Client], "_MonkeyPatchedWSGIResponse"]

COVERED = {
    "CheckInPage", "CompletePage", "NoShowPage", "CancelPage", "ReviewStepPage",
    "RescheduleReviewPage", "WaitlistAddPage", "OfferPage", "AcceptPage", "RemindersPage",
    "RecordFormPage", "RecordDeletePage", "DeactivatePage",
}  # fmt: skip
NO_REDIRECT = {"AppointmentExportPage"}


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _booked(status: str = "BOOKED") -> Appointment:
    start = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
    row = make(
        "Appointment",
        patient=make_user(full_name=PATIENT_NAME),
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
        status=status,
    )
    assert isinstance(row, Appointment)
    return row


def _status(step: str, before: str = "BOOKED") -> Action:
    return lambda client: admin_post(client, f"{LIST}/{_booked(before).pk}/{step}", {})


def _cancel(client: Client) -> "_MonkeyPatchedWSGIResponse":
    return admin_post(client, f"{LIST}/{_booked().pk}/cancel", {"reason": "Patient asked"})


def _reschedule(client: Client) -> "_MonkeyPatchedWSGIResponse":
    clinic = make_clinic()
    start = datetime(2030, 1, 14, 9, 0, tzinfo=UTC)
    row = make(
        "Appointment", patient=make_user(full_name=PATIENT_NAME), clinician=clinic.clinician,
        appointment_type=clinic.appointment_type, starts_at=start,
        ends_at=start + timedelta(minutes=30),
    )  # fmt: skip
    path = f"{LIST}/{row.pk}/reschedule/review?starts_at=2030-01-14T10:00:00Z"
    return admin_post(client, path, {})


def _book(client: Client) -> "_MonkeyPatchedWSGIResponse":
    clinic = make_clinic({"is_bookable_online": False})
    clinic.patient.full_name = PATIENT_NAME
    clinic.patient.save()
    path = (
        f"{LIST}/new/{clinic.appointment_type.pk}/review?patient={clinic.patient.pk}"
        f"&provider={clinic.clinician.pk}&starts_at=2030-01-14T09:00:00Z"
    )
    return admin_post(client, path, {})


def _waitlist_add(client: Client) -> "_MonkeyPatchedWSGIResponse":
    clinic = make_clinic()
    clinic.patient.full_name = PATIENT_NAME
    clinic.patient.save()
    values = {
        "patient": str(clinic.patient.pk),
        "appointment_type": str(clinic.appointment_type.pk),
        "preferred_clinician": "",
        "earliest_at": "2030-01-06T09:00",
        "latest_at": "2030-01-08T09:00",
    }
    return admin_post(client, f"{WAITLIST}/new", values)


def _waitlist_offer(client: Client) -> "_MonkeyPatchedWSGIResponse":
    clinic = make_clinic()
    clinic.patient.full_name = PATIENT_NAME
    clinic.patient.save()
    _cancelled_slot(clinic)
    return admin_post(client, f"{WAITLIST}/{_entry_for(clinic).pk}/offer", {})


def _waitlist_accept(client: Client) -> "_MonkeyPatchedWSGIResponse":
    clinic = make_clinic()
    clinic.patient.full_name = PATIENT_NAME
    clinic.patient.save()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    return admin_post(client, f"{WAITLIST}/{entry.pk}/accept", {})


def _reminders(client: Client) -> "_MonkeyPatchedWSGIResponse":
    return admin_post(client, "/admin-console/settings/reminders", {})


def _specialty_new(client: Client) -> "_MonkeyPatchedWSGIResponse":
    form = {"name": "Neurology", "code": "Neurology", "is_active": "on"}
    return admin_post(client, "/admin-console/specialties/new", form)


def _specialty_edit(client: Client) -> "_MonkeyPatchedWSGIResponse":
    row = make("Specialty", name="Cardiology")
    assert isinstance(row, Specialty)
    form = {
        "name": "Neurology",
        "code": "Neurology",
        "is_active": "on",
        "version": str(row.version),
    }
    return admin_post(client, f"/admin-console/specialties/{row.pk}/edit", form)


def _specialty_delete(client: Client) -> "_MonkeyPatchedWSGIResponse":
    row = make("Specialty", name="Cardiology")
    return admin_post(client, f"/admin-console/specialties/{row.pk}/delete", {})


def _deactivate(client: Client) -> "_MonkeyPatchedWSGIResponse":
    row = make("User", role="PATIENT", full_name=PATIENT_NAME)
    assert isinstance(row, User)
    path = f"/admin-console/users/{row.pk}/deactivate"
    return admin_post(client, path, {"version": str(row.version)})


CASES: dict[str, tuple[Action, str]] = {
    "check_in": (_status("check-in"), f"Checked in the appointment of {PATIENT_NAME}."),
    "complete": (
        _status("complete", "CHECKED_IN"),
        f"Completed the appointment of {PATIENT_NAME}.",
    ),
    "no_show": (_status("no-show"), f"Marked as no-show the appointment of {PATIENT_NAME}."),
    "cancel": (_cancel, f"Cancelled the appointment of {PATIENT_NAME}."),
    "reschedule": (_reschedule, f"Rescheduled the appointment of {PATIENT_NAME}."),
    "book": (_book, f"Booked an appointment for {PATIENT_NAME}."),
    "waitlist_add": (_waitlist_add, f"Added {PATIENT_NAME} to the waitlist."),
    "waitlist_offer": (_waitlist_offer, f"Offered a time to {PATIENT_NAME}."),
    "waitlist_accept": (_waitlist_accept, f"Accepted the offer for {PATIENT_NAME}."),
    "reminders": (_reminders, "0 reminders created."),
    "record_create": (_specialty_new, "Created the specialty Neurology."),
    "record_update": (_specialty_edit, "Saved the specialty Neurology."),
    "record_delete": (_specialty_delete, "Deleted the specialty."),
    "user_deactivate": (_deactivate, f"Deactivated {PATIENT_NAME}."),
}


@pytest.mark.parametrize("name", CASES)
def returns_a_notice_once_with_what_was_done_when_the_admin_acts(name: str) -> None:
    action, sentence = CASES[name]
    client = admin_client()

    response = action(client)
    first = client.get(response["Location"]).content.decode()
    second = client.get(response["Location"]).content.decode()

    assert response.status_code == 303
    assert sentence in first.replace("&#x27;", "'")
    assert sentence not in second.replace("&#x27;", "'")


def returns_no_notice_when_the_address_or_a_forged_cookie_carries_words() -> None:
    client = admin_client()
    client.cookies[ADMIN_NOTICE_COOKIE] = "Deleted everything."

    html = client.get("/admin-console/", {"notice": "Deleted everything."}).content.decode()

    assert "Deleted everything" not in html


def _post_view_classes(patterns: list[URLPattern | URLResolver], prefix: str = "") -> set[str]:
    found: set[str] = set()
    for entry in patterns:
        route = prefix + str(entry.pattern)
        if isinstance(entry, URLResolver):
            found |= _post_view_classes(list(entry.url_patterns), route)
            continue
        view_class = getattr(entry.callback, "view_class", None)
        if route.startswith("admin-console") and view_class and hasattr(view_class, "post"):
            found.add(view_class.__name__)
    return found


def returns_every_admin_post_route_in_the_notice_list_or_the_download_list() -> None:
    posted = _post_view_classes(list(get_resolver().url_patterns))

    assert posted - COVERED - NO_REDIRECT == set()


def returns_a_cookie_without_the_patient_name_when_the_admin_acts() -> None:
    client = admin_client()

    response = _status("check-in")(client)

    cookie = response.cookies[ADMIN_NOTICE_COOKIE].value
    assert PATIENT_NAME not in cookie
    assert PATIENT_NAME not in str(signing.loads(cookie, salt=NOTICE_SALT))
