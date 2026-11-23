"""Section 7.1: a week of free slots in the hospital's zone."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time

import pytest
from django.test import Client

from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, no_inline_code, times_path

pytestmark = pytest.mark.django_db

# 08:00 to 10:00 Berlin is 07:00 to 09:00 UTC: the 07:00 and 07:30 starts fall inside
# the 120 minute lead time from 06:00 UTC; 08:00 is exactly at its edge and stays offered.
LEAD_TIME_RULE = {"start_time": time(8, 0), "end_time": time(10, 0), "slot_step_minutes": 30}


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


def returns_next_week_link_and_no_previous_when_previous_week_is_past() -> None:
    clinic = make_clinic()

    html = Client().get(times_path(clinic, "?week=2030-01-09")).content.decode()

    assert "week=2030-01-14" in html
    assert 'rel="prev"' not in html


def returns_no_previous_link_when_previous_week_ends_before_today_in_hospital_zone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 23:30 UTC on Sunday is 00:30 on Monday in Berlin: the week before today ends on Sunday.
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 6, 23, 30, tzinfo=UTC))
    clinic = make_clinic()

    html = Client().get(times_path(clinic, "?week=2030-01-07")).content.decode()

    assert 'rel="prev"' not in html


def returns_previous_link_when_previous_week_still_contains_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sunday 13 January: the week of 7 to 13 January still contains today, so its link stays.
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 13, 12, 0, tzinfo=UTC))
    clinic = make_clinic()

    html = Client().get(times_path(clinic, "?week=2030-01-14")).content.decode()

    previous = re.search(r'href="([^"]+)" rel="prev"', html)
    assert previous is not None
    assert "week=2030-01-07" in previous.group(1)


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


def returns_week_of_first_free_time_when_current_week_has_none_and_week_is_not_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 13, 12, 0, tzinfo=UTC))
    clinic = make_clinic()

    html = Client().get(times_path(clinic)).content.decode()

    assert "Mon 14 Jan" in html
    assert "week=2030-01-21" in html


def returns_no_time_inside_lead_time_on_the_times_page_for_a_visitor() -> None:
    clinic = make_clinic(rule_fields=LEAD_TIME_RULE)
    provider = clinic.clinician.pk

    html = Client().get(times_path(clinic, f"?provider={provider}")).content.decode()

    assert "starts_at=2030-01-07T07:00:00Z" not in html
    assert "starts_at=2030-01-07T08:00:00Z" in html
