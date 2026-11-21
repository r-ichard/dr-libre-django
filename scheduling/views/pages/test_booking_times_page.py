"""Task 12a, times: a week of free slots in the hospital's zone."""

from __future__ import annotations

import re
from datetime import date

import pytest
from django.test import Client

from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, times_path

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def returns_week_of_slots_naming_zone_type_duration_provider_hospital_and_address() -> None:
    clinic = make_clinic()
    provider = clinic.clinician.pk

    response = Client().get(times_path(clinic, f"?provider={provider}"))

    html = response.content.decode()
    assert response.status_code == 200
    assert "Europe/Berlin" in html
    assert clinic.appointment_type.name in html
    assert "30 minutes" in html
    assert "Riverside Hospital" in html
    assert "1 River Road" in html
    assert len(re.findall(r"<h1", html)) == 1
    assert no_inline_code(html)


def returns_links_to_details_with_provider_and_start_when_slot_is_listed() -> None:
    clinic = make_clinic()
    provider = clinic.clinician.pk

    html = Client().get(times_path(clinic, f"?provider={provider}")).content.decode()

    base = f"/book/{clinic.appointment_type.pk}/details"
    link = f"{base}?provider={provider}&amp;starts_at=2030-01-07T10:00:00Z"
    assert link in html
    assert "11:00" in html


def returns_previous_and_next_week_links() -> None:
    clinic = make_clinic()

    html = Client().get(times_path(clinic, "?week=2030-01-09")).content.decode()

    assert "week=2030-01-14" in html
    assert "week=2029-12-31" in html


def returns_first_available_slots_when_no_provider_given() -> None:
    clinic = make_clinic()

    html = Client().get(times_path(clinic)).content.decode()

    assert "2030-01-07T10:00:00Z" in html


def returns_404_when_type_or_provider_is_unknown() -> None:
    clinic = make_clinic()
    unknown = "00000000-0000-4000-8000-000000000000"

    known = Client().get(times_path(clinic))
    no_type = Client().get(f"/book/{unknown}")
    no_provider = Client().get(times_path(clinic, f"?provider={unknown}"))

    assert (known.status_code, no_type.status_code, no_provider.status_code) == (200, 404, 404)


def returns_current_week_when_week_is_not_a_date() -> None:
    clinic = make_clinic()

    response = Client().get(times_path(clinic, "?week=nonsense"))

    assert response.status_code == 200
    assert "2030-01-07T10:00:00Z" in response.content.decode()


def returns_empty_state_with_next_week_link_when_week_has_no_slots() -> None:
    clinic = make_clinic(rule_fields={"valid_to": date(2030, 1, 8)})

    html = (
        Client()
        .get(times_path(clinic, "?week=2030-01-16&provider=" + str(clinic.clinician.pk)))
        .content.decode()
    )

    assert "No free times this week" in html
    assert "week=2030-01-21" in html
