"""Task 11: provider, hospital and specialty pages, open to everyone, fetched as a browser does
(cross-site check enforced, Origin set)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from scheduling.models import ClinicianProfile
from scheduling.models.builders import add_clinician, make
from scheduling.models.organisation import AppointmentType
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import no_inline_code
from scheduling.views.pages.browser_support import SITE_ORIGIN, browser_client
from scheduling.views.pages.search_pages_support import (
    HOUR_OF_SLOTS,
    NOW,
    PLANTED_BIRTH,
    PLANTED_EMAIL,
    PLANTED_PATIENT,
    PLANTED_PHONE,
    PLANTED_REASON,
    plant_clinic,
    update_row,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

PRIVATE_VALUES = (PLANTED_EMAIL, PLANTED_PHONE, PLANTED_BIRTH, PLANTED_PATIENT, PLANTED_REASON)
NO_SLOTS_TEXT = "No availability in the next 90 days"
PAGE_KINDS = ["providers", "hospitals", "specialties"]
SLOT_LINK = re.compile(
    r'<a class="[^"]*slot-link[^"]*" href="[^"]+">([^<]+)'
    r'<span class="visually-hidden">([^<]+)</span></a>'
)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _get(path: str) -> _MonkeyPatchedWSGIResponse:
    return browser_client().get(path, headers={"Origin": SITE_ORIGIN})


def _html(path: str) -> str:
    response = _get(path)
    assert response.status_code == 200, path
    return unescape(response.content.decode())


def _path(kind: str, clinician: ClinicianProfile) -> str:
    identifiers = {
        "providers": clinician.pk,
        "hospitals": clinician.department.hospital.pk,
        "specialties": clinician.specialty.pk,
    }
    return f"/{kind}/{identifiers[kind]}"


def _planted() -> tuple[ClinicianProfile, AppointmentType]:
    clinician, appointment_type = plant_clinic()
    update_row(clinician, title="Dr", bio="Pioneer of the analytical engine.")
    update_row(
        clinician.department.hospital,
        phone="+49 30 HOSPITAL-LINE",
        description="A teaching hospital on the river.",
    )
    return clinician, appointment_type


def returns_provider_page_with_name_title_specialty_bio_department_hospital_and_types() -> None:
    clinician, _ = _planted()

    html = _html(_path("providers", clinician))

    for expected in (
        "Ada Lovelace",
        "Dr",
        clinician.specialty.name,
        "Pioneer of the analytical engine.",
        "Heart Clinic",
        "Riverside General",
        "Check-up",
        "30 minutes",
    ):
        assert expected in html


def returns_hospital_zone_name_on_every_page() -> None:
    clinician, _ = _planted()

    for kind in PAGE_KINDS:
        assert "Europe/Berlin" in _html(_path(kind, clinician)), kind


def returns_week_strip_monday_to_sunday_with_next_link_on_the_provider_page() -> None:
    clinician, appointment_type = _planted()
    base = f"/providers/{clinician.pk}"

    html = _html(base)

    days = re.findall(r'<h3 class="week-strip__heading">([^<]+)</h3>', html)
    assert [day.split()[0] for day in days] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    following = re.search(r'href="([^"]+)" rel="next"', html)
    assert following is not None
    assert following.group(1).startswith(f"{base}?")
    assert f"type={appointment_type.pk}" in following.group(1)
    assert "week=2030-01-14" in following.group(1)
    assert 'rel="prev"' not in html


def returns_previous_link_with_type_on_the_provider_page_when_week_follows_today() -> None:
    clinician, appointment_type = _planted()
    base = f"/providers/{clinician.pk}"

    html = _html(f"{base}?week=2030-01-14")

    previous = re.search(r'href="([^"]+)" rel="prev"', html)
    assert previous is not None
    assert previous.group(1).startswith(f"{base}?")
    assert f"type={appointment_type.pk}" in previous.group(1)
    assert "week=2030-01-07" in previous.group(1)


def returns_the_asked_week_when_week_is_given() -> None:
    clinician, _ = _planted()

    html = _html(f"/providers/{clinician.pk}?week=2030-01-14")

    assert "14 Jan" in html
    assert 'href="/providers/' in html


def returns_current_week_when_week_is_far_outside_the_horizon_or_garbage() -> None:
    clinician, _ = _planted()
    base = f"/providers/{clinician.pk}"

    for week in ("1900-01-01", "9999-12-31", "nonsense"):
        assert "7 Jan" in _html(f"{base}?week={week}"), week


def returns_types_switch_with_aria_current_and_no_current_text() -> None:
    clinician, first_type = _planted()
    second = make("AppointmentType", department=clinician.department, name="Follow-up")
    update_row(second, duration_minutes=90)

    html = _html(f"/providers/{clinician.pk}?type={second.pk}")

    nav = re.search(r'<nav[^>]*aria-label="[^"]*type[^"]*"[^>]*>.*?</nav>', html, re.DOTALL | re.I)
    assert nav is not None
    assert nav.group(0).count('aria-current="page"') == 1
    assert "(current)" not in nav.group(0)
    assert f"type={first_type.pk}" in nav.group(0)
    assert f"/book/{second.pk}/details?provider={clinician.pk}&" in html


def returns_shortest_type_when_asked_type_is_unknown_or_not_the_providers() -> None:
    clinician, appointment_type = _planted()
    other = make("AppointmentType", name="Foreign Type")

    for asked in (uuid4(), other.pk, "garbage"):
        html = _html(f"/providers/{clinician.pk}?type={asked}")
        assert f"/book/{appointment_type.pk}/details?provider={clinician.pk}&" in html
        assert "Foreign Type" not in html


def returns_details_page_naming_provider_and_slot_when_provider_slot_followed() -> None:
    clinician, appointment_type = _planted()
    html = _html(f"/providers/{clinician.pk}")
    link = re.search(rf'href="(/book/{appointment_type.pk}/details\?[^"]+)"', html)
    assert link is not None

    response = _get(link.group(1))

    assert response.status_code == 200
    assert "Ada Lovelace" in response.content.decode()


def returns_no_availability_text_when_nothing_free_in_90_days() -> None:
    clinician, _ = _planted()
    clinician.availabilityrule_set.all().delete()

    for kind in ("providers", "hospitals"):
        assert NO_SLOTS_TEXT in _html(_path(kind, clinician)), kind


def returns_first_available_link_per_type_with_no_provider_when_hospital_page_opened() -> None:
    clinician, appointment_type = _planted()

    html = _html(_path("hospitals", clinician))

    assert f'href="/book/{appointment_type.pk}"' in html
    assert "First available" in html
    assert "Check-up" in html
    assert _get(f"/book/{appointment_type.pk}").status_code == 200


def returns_first_available_link_naming_the_department_when_type_names_repeat() -> None:
    clinician, _ = _planted()
    other_department = make(
        "Department", hospital=clinician.department.hospital, name="Lung Clinic"
    )
    make("AppointmentType", department=other_department, name="Check-up")
    add_clinician(other_department, HOUR_OF_SLOTS)

    html = _html(_path("hospitals", clinician))

    links = re.findall(r"First available: Check-up<span[^>]*> in ([^<]+)</span>", html)
    assert sorted(links) == ["Heart Clinic", "Lung Clinic"]
    assert "Heart Clinic" in html
    assert "Lung Clinic" in html


def returns_hospital_page_with_address_phone_description_departments_specialties_providers() -> (
    None
):
    clinician, _ = _planted()

    html = _html(_path("hospitals", clinician))

    for expected in (
        "Riverside General",
        "1 River Road",
        "Berlin",
        "+49 30 HOSPITAL-LINE",
        "A teaching hospital on the river.",
        "Heart Clinic",
        clinician.specialty.name,
        "Ada Lovelace",
    ):
        assert expected in html
    assert re.search(r"<h1[^>]*>[^<]*Riverside General", html)


def returns_only_that_specialty_with_pagination_on_its_own_path_on_the_specialty_page() -> None:
    clinician, _ = _planted()
    other_user = make("User", role="CLINICIAN", full_name="Grace Hopper")
    add_clinician(clinician.department, HOUR_OF_SLOTS, user=other_user)
    path = _path("specialties", clinician)

    html = _html(f"{path}?page_size=10")

    assert "Ada Lovelace" in html
    assert "Grace Hopper" not in html
    assert f'href="{path}?page_size=50"' in html


def returns_404_page_when_inactive_or_unlisted() -> None:
    clinician, appointment_type = _planted()
    paths = {kind: _path(kind, clinician) for kind in PAGE_KINDS}
    update_row(appointment_type, is_bookable_online=False)
    assert _get(paths["providers"]).status_code == 404
    update_row(appointment_type, is_bookable_online=True)
    update_row(clinician.department.hospital, is_active=False)
    update_row(clinician.specialty, is_active=False)

    assert [_get(path).status_code for path in paths.values()] == [404, 404, 404]


@pytest.mark.parametrize("kind", PAGE_KINDS)
def returns_404_page_when_id_is_unknown(kind: str) -> None:
    plant_clinic()

    response = _get(f"/{kind}/{uuid4()}")

    assert response.status_code == 404
    assert "Ada Lovelace" not in response.content.decode()


def returns_own_title_and_meta_description_per_page() -> None:
    clinician, _ = _planted()
    titles: list[str] = []
    descriptions: list[str] = []

    for kind in PAGE_KINDS:
        html = _html(_path(kind, clinician))
        title = re.search(r"<title>([^<]+)</title>", html)
        description = re.search(r'<meta name="description" content="([^"]{20,})">', html)
        assert title is not None and description is not None, kind
        titles.append(title.group(1))
        descriptions.append(description.group(1))

    assert "Ada Lovelace" in titles[0]
    assert "Riverside General" in titles[1]
    assert clinician.specialty.name in titles[2]
    assert len(set(titles)) == len(set(descriptions)) == 3


def returns_single_h1_and_labelled_landmarks_and_ordered_headings() -> None:
    clinician, _ = _planted()

    for kind in PAGE_KINDS:
        html = _html(_path(kind, clinician))
        assert len(re.findall(r"<h1", html)) == 1, kind
        assert "<main" in html
        for nav in re.findall(r"<nav[^>]*>", html):
            assert 'aria-label="' in nav, (kind, nav)
        levels = [int(level) for level in re.findall(r"<h([1-6])[ >]", html)]
        for before, after in zip(levels, levels[1:], strict=False):
            assert after <= before + 1, (kind, levels)


def returns_no_inline_script_or_style() -> None:
    clinician, _ = _planted()

    for kind in PAGE_KINDS:
        assert no_inline_code(_html(_path(kind, clinician))), kind


def returns_no_clinician_email_phone_birth_date_or_patient_data() -> None:
    clinician, _ = _planted()

    for kind in PAGE_KINDS:
        html = _html(_path(kind, clinician))
        assert "Ada Lovelace" in html
        assert [value for value in PRIVATE_VALUES if value in html] == []


def returns_slot_link_name_containing_visible_text_on_each_page() -> None:
    clinician, _ = _planted()

    for kind in PAGE_KINDS:
        html = _html(_path(kind, clinician))
        links = SLOT_LINK.findall(html)
        assert links, kind
        for visible, hidden in links:
            assert re.fullmatch(r"[A-Z][a-z]{2} \d{1,2} [A-Z][a-z]{2}, \d\d:\d\d", visible)
            assert hidden == " with Dr Ada Lovelace"
    assert 'aria-hidden="true">Mon' not in html


def returns_links_from_search_cards_to_provider_hospital_and_specialty_pages() -> None:
    clinician, _ = _planted()
    expected = {
        "providers": [
            _path("providers", clinician),
            _path("hospitals", clinician),
            _path("specialties", clinician),
        ],
        "hospitals": [_path("hospitals", clinician)],
        "specialties": [_path("specialties", clinician)],
    }

    for kind, paths in expected.items():
        html = _html(f"/?list={kind}")
        for path in paths:
            assert f'href="{path}"' in html, (kind, path)


def returns_links_between_detail_pages_where_they_name_one_another() -> None:
    clinician, _ = _planted()
    provider, hospital, specialty = (_path(kind, clinician) for kind in PAGE_KINDS)

    assert f'href="{hospital}"' in _html(provider)
    assert f'href="{specialty}"' in _html(provider)
    assert f'href="{provider}"' in _html(hospital)
    assert f'href="{specialty}"' in _html(hospital)
    assert f'href="{provider}"' in _html(specialty)
    assert f'href="{hospital}"' in _html(specialty)


def returns_hospital_meta_description_and_empty_state_when_no_provider_is_bookable() -> None:
    clinician, _ = _planted()
    html = _html(_path("hospitals", clinician))
    description = re.search(r'<meta name="description" content="([^"]+)">', html)
    assert description is not None and "Riverside General" in description.group(1)

    empty_hospital = make("Hospital", name="Quiet Hospital")

    quiet = _html(f"/hospitals/{empty_hospital.pk}")

    assert "No providers to book online" in quiet
    assert "First available" not in quiet
    assert 'class="card result"' not in quiet


def returns_week_of_first_free_time_on_provider_page_when_current_week_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: datetime(2030, 1, 13, 12, 0, tzinfo=UTC))
    clinician, _ = _planted()

    html = _html(f"/providers/{clinician.pk}")

    following = re.search(r'href="([^"]+)" rel="next"', html)
    previous = re.search(r'href="([^"]+)" rel="prev"', html)
    assert following is not None and "week=2030-01-21" in following.group(1)
    assert previous is not None and "week=2030-01-07" in previous.group(1)
