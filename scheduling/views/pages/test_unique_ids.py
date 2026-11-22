"""Task 17c, #28: an id is unique on every page the product renders. Each page route needs a
fixture here, so a new page cannot skip the check."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.models import Appointment, User
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

ID_PATTERN = re.compile(r"""\sid=["']([^"']*)["']""")
NOT_PAGES = ("api/", "static/", "favicon.ico", "style")
NOT_HTML = {"clinician/type-colours.css", "appointments/<uuid:appointment_id>/calendar.ics"}
ZERO_UUID = "00000000-0000-4000-8000-000000000000"


@dataclass(frozen=True)
class World:
    clinic: Clinic
    appointment: Appointment
    admin: User


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _routes(patterns: list[URLPattern | URLResolver], prefix: str = "") -> list[str]:
    found = []
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            found.extend(_routes(list(pattern.url_patterns), route))
        else:
            found.append(route)
    return found


def _page_routes() -> list[str]:
    return [
        route
        for route in _routes(list(get_resolver().url_patterns))
        if not route.startswith(NOT_PAGES) and route not in NOT_HTML and not route.startswith("^")
    ]


def _world() -> World:
    clinic = make_clinic()
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    admin = make("User", role="ADMIN")
    assert isinstance(appointment, Appointment) and isinstance(admin, User)
    return World(clinic, appointment, admin)


def _client_for(route: str, world: World) -> Client:
    if route.startswith("clinician/"):
        user = world.clinic.clinician.user
        assert isinstance(user, User)
        return signed_in_patient(user)
    if route.startswith("admin-console"):
        return signed_in_patient(world.admin)
    if route.startswith(("patient/", "appointments/")):
        return signed_in_patient(world.clinic.patient)
    return Client()


def _path_of(route: str, world: World) -> str:
    ids = {
        "appointment_id": world.appointment.pk,
        "appointment_type_id": world.clinic.appointment_type.pk,
        "provider_id": world.clinic.clinician.pk,
        "hospital_id": world.clinic.department.hospital_id,
    }
    return re.sub(
        r"<uuid:(\w+)>", lambda found: str(ids.get(found.group(1), ZERO_UUID)), "/" + route
    )


def _duplicates(html: str) -> list[str]:
    return [name for name, count in Counter(ID_PATTERN.findall(html)).items() if count > 1]


def returns_no_duplicate_id_when_any_page_renders() -> None:
    world = _world()
    rendered = 0
    problems: dict[str, list[str]] = {}

    for route in _page_routes():
        response = _client_for(route, world).get(_path_of(route, world))
        assert response.status_code < 500, route
        rendered += 1
        duplicates = _duplicates(response.content.decode())
        if duplicates:
            problems[route] = duplicates

    assert rendered > 30
    assert problems == {}


def returns_no_duplicate_id_when_time_off_form_answers_422() -> None:
    clinic = make_clinic()
    user = clinic.clinician.user
    assert isinstance(user, User)
    form = {"starts_at": "", "ends_at": "", "reason": ""}

    response = browser_post(signed_in_patient(user), "/clinician/time-off", form)

    assert response.status_code == 422
    assert _duplicates(response.content.decode()) == []
