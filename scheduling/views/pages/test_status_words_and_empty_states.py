"""Sections 5.6 and 16: every status is a badge with a word wherever it is rendered, and
every list page says what is missing when it has nothing to show."""

from __future__ import annotations

import re

import pytest
from django.db.models import F
from django.test import Client

from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.models.builders import make, make_clinic, make_user
from scheduling.views import clock
from scheduling.views.pages.admin_record_kinds import KIND_VIEWS, KindView
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.page_walk_support import client_for_role, make_world

pytestmark = pytest.mark.django_db

ADMIN_APPOINTMENTS = "/admin-console/appointments"
NO_MATCH = "?q=zzzz-no-match"
APPOINTMENT_WORDS = {
    AppointmentStatus.BOOKED: "Booked",
    AppointmentStatus.CONFIRMED: "Confirmed",
    AppointmentStatus.CHECKED_IN: "Checked in",
    AppointmentStatus.COMPLETED: "Completed",
    AppointmentStatus.CANCELLED: "Cancelled",
    AppointmentStatus.NO_SHOW: "No-show",
}
EMPTY_LISTS = {
    "admin": [
        "/admin-console/",
        ADMIN_APPOINTMENTS,
        "/admin-console/waitlist",
    ],
    "patient": ["/patient/appointments", "/patient/waitlist", "/patient/notifications"],
    "clinician": [
        "/clinician/patients",
        "/clinician/availability",
        "/clinician/time-off",
        "/clinician/rooms",
    ],
}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _badge_words(html: str) -> list[str]:
    spans = re.findall(r'<span class="badge[^"]*">(.*?)</span>', html, re.S)
    return [re.sub(r"<[^>]+>", "", span).strip() for span in spans]


def returns_a_badge_with_the_word_when_an_admin_list_shows_active_and_inactive() -> None:
    world = make_world()
    make("Room")
    client = client_for_role("admin", world)
    problems = []

    for view in KIND_VIEWS.values():
        if view.kind == "department":
            continue  # the model has no active flag, so it has no status to show
        words = _badge_words(client.get(f"/admin-console/{view.path_name}").content.decode())
        if "Active" not in words:
            problems.append(view.path_name)

    assert problems == []


def returns_success_and_pending_badges_when_a_list_shows_active_and_inactive() -> None:
    world = make_world()
    make("Room")
    make("Room", is_active=False)
    client = client_for_role("admin", world)

    html = client.get("/admin-console/rooms").content.decode()

    assert re.search(r'<span class="badge badge--success">.*?Active</span>', html, re.S)
    assert re.search(r'<span class="badge badge--pending">.*?Inactive</span>', html, re.S)


def returns_a_badge_with_the_word_when_the_admin_appointment_list_shows_each_status() -> None:
    world = make_world()
    client = client_for_role("admin", world)
    shown = []

    for status, word in APPOINTMENT_WORDS.items():
        cancelled = status == AppointmentStatus.CANCELLED
        Appointment.objects.update(
            status=status,
            version=F("version") + 1,
            cancelled_at=NOW if cancelled else None,
            cancellation_reason="Asked to" if cancelled else "",
        )
        words = _badge_words(client.get(ADMIN_APPOINTMENTS).content.decode())
        shown.append((status, word in words))

    assert shown == [(status, True) for status in APPOINTMENT_WORDS]


def returns_the_dashboard_empty_state_when_no_day_has_an_appointment() -> None:
    admin = signed_in_patient(make_user(role="ADMIN"))

    html = admin.get("/admin-console/").content.decode()

    assert "Appointments per day" in html
    assert 'class="empty-state"' in html


@pytest.mark.parametrize("role", sorted(EMPTY_LISTS))
@pytest.mark.parametrize("query", ["", NO_MATCH])
def returns_an_empty_state_when_a_list_page_has_nothing_to_show(role: str, query: str) -> None:
    clinic = make_clinic()
    clinic.clinician.availabilityrule_set.all().delete()
    users = {
        "admin": make_user(role="ADMIN"),
        "patient": clinic.patient,
        "clinician": clinic.clinician.user,
    }
    client = signed_in_patient(users[role])
    without = [
        path
        for path in EMPTY_LISTS[role]
        if 'class="empty-state"' not in client.get(path + query).content.decode()
    ]

    assert without == []


@pytest.mark.parametrize("view", list(KIND_VIEWS.values()), ids=lambda view: view.path_name)
def returns_an_empty_state_when_an_admin_record_list_finds_nothing(view: KindView) -> None:
    client = signed_in_patient(make_user(role="ADMIN"))

    html = client.get(f"/admin-console/{view.path_name}{NO_MATCH}").content.decode()

    assert 'class="empty-state"' in html


def returns_an_empty_state_when_a_public_search_finds_nothing() -> None:
    html = Client().get("/?q=zzzz-no-match").content.decode()

    assert 'class="empty-state"' in html
