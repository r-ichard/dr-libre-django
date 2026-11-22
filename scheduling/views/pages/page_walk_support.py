"""Every page route of the URL configuration, with a world to fill its parameters and a client
per role. Shared by the walking tests, so a new page is covered by all of them."""

from __future__ import annotations

import re
from dataclasses import dataclass

from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.models import Appointment, User
from scheduling.models.builders import Clinic, make, make_clinic
from scheduling.views.pages.booking_pages_support import signed_in_patient

NOT_PAGES = ("api/", "static/", "favicon.ico", "style")
NOT_HTML = {"clinician/type-colours.css", "appointments/<uuid:appointment_id>/calendar.ics"}
ZERO_UUID = "00000000-0000-4000-8000-000000000000"
ROLES = ("signed_out", "patient", "clinician", "admin")


@dataclass(frozen=True)
class World:
    clinic: Clinic
    appointment: Appointment
    admin: User


def _routes(patterns: list[URLPattern | URLResolver], prefix: str = "") -> list[str]:
    found = []
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            found.extend(_routes(list(pattern.url_patterns), route))
        else:
            found.append(route)
    return found


def page_routes() -> list[str]:
    return [
        route
        for route in _routes(list(get_resolver().url_patterns))
        if not route.startswith(NOT_PAGES) and route not in NOT_HTML and not route.startswith("^")
    ]


def make_world() -> World:
    clinic = make_clinic()
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
    )
    admin = make("User", role="ADMIN")
    make(
        "Notification",
        recipient=clinic.patient,
        title="Appointment booked",
        body="Your appointment is booked.",
        appointment=appointment,
    )
    assert isinstance(appointment, Appointment) and isinstance(admin, User)  # noqa: S101 - broken setup
    return World(clinic, appointment, admin)


def client_for_role(role: str, world: World) -> Client:
    if role == "clinician":
        user = world.clinic.clinician.user
        assert isinstance(user, User)  # noqa: S101 - broken setup
        return signed_in_patient(user)
    if role == "admin":
        return signed_in_patient(world.admin)
    if role == "patient":
        return signed_in_patient(world.clinic.patient)
    return Client()


def client_for_route(route: str, world: World) -> Client:
    if route.startswith("clinician/"):
        return client_for_role("clinician", world)
    if route.startswith("admin-console"):
        return client_for_role("admin", world)
    if route.startswith(("patient/", "appointments/")):
        return client_for_role("patient", world)
    return Client()


def path_of(route: str, world: World) -> str:
    ids = {
        "appointment_id": world.appointment.pk,
        "appointment_type_id": world.clinic.appointment_type.pk,
        "provider_id": world.clinic.clinician.pk,
        "hospital_id": world.clinic.department.hospital_id,
    }
    return re.sub(
        r"<uuid:(\w+)>", lambda found: str(ids.get(found.group(1), ZERO_UUID)), "/" + route
    )
