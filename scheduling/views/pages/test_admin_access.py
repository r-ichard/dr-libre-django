"""Section 12.3: only an admin reaches the admin console. The routes come from
the URL configuration, so a route added later is covered without touching this file."""

import re
from collections.abc import Iterator

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from scheduling.models import Hospital
from scheduling.views.pages.admin_support import admin_client, client_of_role

pytestmark = pytest.mark.django_db

CONSOLE = "admin-console/"
# One fixed id: workers of a parallel run must collect the same test ids.
SOME_ID = "6f1c3a52-0d1e-4b8a-9c53-2f7d1b0e4a11"
RECORD_KINDS = 7
ROUTES_PER_KIND = 5
# Task 19: 3. Task 20: 6 appointment, 5 booking, 2 reschedule, 1 audit, 2 settings, 4 waitlist.
# Task 21: 1 export (the dashboard replaces the home).
EXTRA_ROUTES = 24


def _templates(patterns: list[URLPattern | URLResolver], prefix: str = "") -> Iterator[str]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _templates(list(entry.url_patterns), prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern)


def _console_paths() -> list[str]:
    found = {
        "/" + re.sub(r"<uuid:\w+>", SOME_ID, template)
        for template in _templates(list(get_resolver().url_patterns))
        if template.startswith(CONSOLE)
    }
    return sorted(found)


def returns_the_console_home_and_the_record_routes_when_urls_are_listed() -> None:
    assert len(_console_paths()) == 1 + RECORD_KINDS * ROUTES_PER_KIND + EXTRA_ROUTES


@pytest.mark.parametrize("path", _console_paths())
def returns_sign_in_redirect_to_a_visitor_on_every_console_route(path: str) -> None:
    response = Client().get(path)

    assert response.status_code in (302, 303)
    assert response["Location"].startswith("/sign-in")


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
@pytest.mark.parametrize("path", _console_paths())
def returns_forbidden_page_to_patient_and_clinician_on_every_console_route(
    path: str, role: str
) -> None:
    response = client_of_role(role).get(path)

    assert response.status_code == 403
    assert "Hospitals" not in response.content.decode()


@pytest.mark.parametrize("role", ["PATIENT", "CLINICIAN"])
@pytest.mark.parametrize("path", _console_paths())
def returns_403_to_a_post_from_patient_and_clinician_on_every_console_route(
    path: str, role: str
) -> None:
    response = client_of_role(role).post(path, {"name": "x", "code": "x"})

    assert response.status_code == 403
    assert Hospital.objects.filter(code="x").count() == 0


def returns_200_to_an_admin_on_the_console_home_with_the_navigation() -> None:
    response = admin_client().get("/admin-console/")

    html = response.content.decode()
    assert response.status_code == 200
    for section in ("Hospitals", "Specialties", "Departments", "Rooms", "Appointment types"):
        assert f">{section}<" in html
