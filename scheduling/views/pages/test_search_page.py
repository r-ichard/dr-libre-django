"""Task 10a: the root path is the public search, server-rendered from a plain GET form."""

from __future__ import annotations

import re
from html import unescape

import pytest
from django.test import Client

from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import no_inline_code
from scheduling.views.pages.search_pages_support import (
    FIRST_START,
    NOW,
    PLANTED_BIRTH,
    PLANTED_EMAIL,
    PLANTED_PATIENT,
    PLANTED_PHONE,
    PLANTED_REASON,
    plant_clinic,
)

pytestmark = pytest.mark.django_db

KINDS = ["providers", "hospitals", "specialties"]
PRIVATE_VALUES = (PLANTED_EMAIL, PLANTED_PHONE, PLANTED_BIRTH, PLANTED_PATIENT, PLANTED_REASON)
NO_SLOTS_TEXT = "No availability in the next 90 days"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _root(query: str = "") -> str:
    return Client().get(f"/{query}").content.decode()


def returns_200_without_sign_in_with_title_and_meta_description_at_root() -> None:
    plant_clinic()

    response = Client().get("/")

    html = response.content.decode()
    assert response.status_code == 200
    assert re.search(r"<title>[^<]*[Ss]earch[^<]*</title>", html)
    assert re.search(r'<meta name="description" content="[^"]{20,}">', html)
    assert len(re.findall(r"<h1", html)) == 1


def returns_provider_list_with_the_columns_of_6_2_by_default() -> None:
    clinician, appointment_type = plant_clinic()

    html = _root()

    for expected in (
        "Ada Lovelace",
        "Dr",
        clinician.specialty.name,
        "Riverside General",
        "Heart Clinic",
        "Berlin",
        "Check-up",
        "30 minutes",
        "Europe/Berlin",
    ):
        assert expected in html
    assert len(re.findall(r'href="/book/[^"]+/details\?', html)) == 3


def returns_slot_link_to_details_with_type_provider_and_start_when_slot_is_listed() -> None:
    clinician, appointment_type = plant_clinic()

    html = _root()

    base = f"/book/{appointment_type.pk}/details"
    assert f'href="{base}?provider={clinician.pk}&amp;starts_at={FIRST_START}"' in html
    assert "Mon 7 Jan, 12:00" in html


def returns_all_times_link_to_times_page_for_the_type_and_provider() -> None:
    clinician, appointment_type = plant_clinic()

    html = _root()

    assert f'href="/book/{appointment_type.pk}?provider={clinician.pk}"' in html


def returns_slot_link_name_containing_visible_text_when_rendered() -> None:
    plant_clinic()

    html = _root()

    assert (
        '">Mon 7 Jan, 12:00<span class="visually-hidden"> with Dr Ada Lovelace</span></a>' in html
    )
    assert 'aria-hidden="true">Mon 7 Jan' not in html


def returns_address_street_city_and_counts_on_hospital_list() -> None:
    plant_clinic()

    html = _root("?list=hospitals")

    assert "Riverside General" in html
    assert "1 River Road" in html
    assert "Berlin" in html
    assert "Mon 7 Jan, 11:30" in html
    assert "Europe/Berlin" in html


def returns_provider_count_hospital_count_and_earliest_on_specialty_list() -> None:
    clinician, _ = plant_clinic()

    html = _root("?list=specialties")

    assert clinician.specialty.name in html
    assert "1 provider" in html
    assert "1 hospital" in html
    assert "Mon 7 Jan, 11:30" in html


def returns_no_availability_in_the_next_90_days_when_provider_has_none() -> None:
    clinician, _ = plant_clinic()
    clinician.availabilityrule_set.all().delete()

    html = _root()

    assert NO_SLOTS_TEXT in html


def returns_total_count_page_and_page_count_and_sizes_10_20_50() -> None:
    plant_clinic()

    html = _root("?page_size=10")

    assert "1 result" in html
    assert "Page 1 of 1" in html
    for size in (10, 20, 50):
        assert f"page_size={size}" in html


def returns_every_parameter_in_page_size_links() -> None:
    plant_clinic()

    html = _root("?q=Ada&list=hospitals&sort=name_asc")

    assert "/?q=Ada&amp;list=hospitals&amp;sort=name_asc&amp;page_size=50" in html


def returns_same_results_when_address_is_shared() -> None:
    plant_clinic()
    address = "/?q=Ada&sort=name_asc&page_size=10"

    first = Client().get(address).content
    second = Client().get(address).content

    assert first == second
    assert b"Ada Lovelace" in first


def returns_default_filters_silently_when_values_are_invalid() -> None:
    plant_clinic()
    query = "?specialty=x&hospital=y&from=nope&window=z&time_of_day=q&page=-3&sort=bad&list=bad"

    response = Client().get(f"/{query}")

    html = response.content.decode()
    assert response.status_code == 200
    assert "Ada Lovelace" in html
    assert "error" not in html.lower()


def returns_distance_sort_only_when_location_is_in_the_address() -> None:
    plant_clinic()

    without = _root()
    with_location = _root("?latitude=52.5&longitude=13.4")

    assert 'value="distance"' not in without
    assert 'value="distance"' in with_location


def returns_wider_link_without_filters_when_filters_set() -> None:
    plant_clinic()

    html = _root("?q=zzzznomatch&window=today&list=hospitals")

    assert "Ada Lovelace" not in html
    assert 'href="/?q=zzzznomatch&amp;list=hospitals"' in html


def returns_wider_link_without_text_when_no_filters() -> None:
    plant_clinic()

    html = _root("?q=zzzznomatch&list=hospitals")

    assert 'href="/?list=hospitals"' in html
    assert 'href="/?q=zzzznomatch&amp;list=hospitals">Widen' not in html


def returns_no_wider_link_when_nothing_to_widen() -> None:
    html = _root("?list=hospitals")

    assert "Nothing matches your search" in html
    assert "Widen the search" not in html


def returns_form_as_plain_get_with_a_label_for_every_control() -> None:
    plant_clinic()

    html = _root()

    form = re.search(r"<form[^>]*>.*?</form>", html, re.DOTALL)
    assert form is not None
    assert 'method="get"' in form.group(0)
    assert "csrfmiddlewaretoken" not in form.group(0)
    controls = re.findall(
        r'<(?:input|select)(?![^>]*type="hidden")[^>]*\bid="([^"]+)"', form.group(0)
    )
    assert len(controls) >= 9
    for control_id in controls:
        assert f'for="{control_id}"' in form.group(0)


def returns_no_current_text_in_switch_but_aria_current_and_current_class() -> None:
    plant_clinic()

    html = _root("?list=hospitals")

    nav = re.search(
        r'<nav[^>]*aria-label="[^"]+"[^>]*>(?:(?!</nav>).)*list=hospitals.*?</nav>', html, re.DOTALL
    )
    assert nav is not None
    assert nav.group(0).count('aria-current="page"') == 1
    assert "(current)" not in nav.group(0)
    assert "list-switch__link--current" in nav.group(0)
    assert "list=specialties" in nav.group(0)


def returns_results_in_an_ordered_list_with_icons_hidden_from_readers() -> None:
    plant_clinic()

    html = _root("?list=specialties")

    assert "<ol" in html
    assert re.search(r'<img[^>]*src="/static/icons/specialties/[^"]+\.svg"[^>]*alt=""', html)


def returns_no_inline_code_and_references_the_location_script_by_source() -> None:
    plant_clinic()

    html = _root()

    assert no_inline_code(html)
    assert 'src="/static/js/search_location.js"' in html


def returns_no_clinician_email_phone_birth_date_or_patient_data() -> None:
    plant_clinic()

    for kind in KINDS:
        html = unescape(_root(f"?list={kind}"))
        assert "Riverside General" in html
        for private in (
            PLANTED_EMAIL,
            PLANTED_PHONE,
            PLANTED_BIRTH,
            PLANTED_PATIENT,
            PLANTED_REASON,
        ):
            assert private not in html


def returns_sign_in_link_when_nobody_is_signed_in() -> None:
    plant_clinic()

    html = _root()

    assert re.search(
        r'<header.*<a[^>]*href="/sign-in"[^>]*>Sign in</a>.*</header>', html, re.DOTALL
    )


def returns_no_previous_or_next_link_when_the_only_page_is_shown() -> None:
    plant_clinic()

    html = _root()

    assert 'rel="prev"' not in html
    assert 'rel="next"' not in html
    assert "page=0" not in html
    assert "page=2" not in html


def returns_one_current_page_size_marked_for_the_chosen_size() -> None:
    plant_clinic()

    html = _root("?page_size=50")

    sizes = re.search(r'<nav class="page-sizes".*?</nav>', html, re.DOTALL)
    assert sizes is not None
    current = re.findall(r'<a href="[^"]*"\s+aria-current="true">(\d+)</a>', sizes.group(0))
    assert current == ["50"]
    assert 'name="page_size" value="50"' in html


def returns_summary_and_search_landmark_text_for_the_current_list() -> None:
    plant_clinic()

    html = _root("?list=hospitals")

    assert re.search(r'<p class="results-summary">1 result\. Page 1 of 1\.</p>', html)
    assert 'role="search"' in html
    assert ">Search by name, hospital, city or specialty</label>" in html


def returns_clinician_in_the_earliest_slot_link_of_hospital_and_specialty_lists() -> None:
    clinician, appointment_type = plant_clinic()

    for kind in ("hospitals", "specialties"):
        html = _root(f"?list={kind}")
        assert f"/book/{appointment_type.pk}/details?provider={clinician.pk}&amp;" in html


def returns_icon_of_specialty_code_when_specialty_renamed() -> None:
    clinician, _ = plant_clinic()

    for code, icon in (("general-practice", "general-practice"), ("cardiology", "cardiology")):
        clinician.specialty.code = code
        clinician.specialty.name = "Renamed Specialty"
        clinician.specialty.save()
        assert f"/static/icons/specialties/{icon}.svg" in _root("?list=specialties")
    clinician.specialty.code = "astrology"
    clinician.specialty.name = "Cardiology"
    clinician.specialty.save()
    assert "/static/icons/specialties/fallback.svg" in _root("?list=specialties")
    assert "/static/icons/specialties/cardiology.svg" not in _root("?list=specialties")


def returns_counts_and_no_availability_text_on_hospital_and_specialty_lists() -> None:
    clinician, _ = plant_clinic()

    assert "1 provider, 1 with free times" in _root("?list=hospitals")
    clinician.availabilityrule_set.all().delete()
    for kind in ("hospitals", "specialties"):
        assert NO_SLOTS_TEXT in _root(f"?list={kind}")


def returns_all_times_link_text_naming_the_type_and_hidden_provider() -> None:
    plant_clinic()

    html = _root()

    assert (
        'All times for Check-up<span class="visually-hidden"> with Dr Ada Lovelace</span>' in html
    )


MORE_FILTER_FIELDS = (
    "specialty",
    "hospital",
    "city",
    "appointment_type",
    "from",
    "window",
    "time_of_day",
    "sort",
)


def _form_parts(html: str) -> tuple[str, str, str]:
    form = re.search(r"<form[^>]*>.*?</form>", html, re.DOTALL)
    assert form is not None
    details = re.search(r"<details[^>]*>.*?</details>", form.group(0), re.DOTALL)
    assert details is not None
    return form.group(0), details.group(0), form.group(0).replace(details.group(0), "")


def returns_q_field_and_search_button_before_more_filters_disclosure() -> None:
    plant_clinic()

    form, details, outside = _form_parts(_root())

    assert 'name="q"' in outside
    assert 'type="submit"' in outside
    assert form.index('name="q"') < form.index('type="submit"') < form.index("<details")
    assert "More filters" in details
    assert "<summary" in details
    assert 'name="q"' not in details
    for field in MORE_FILTER_FIELDS:
        assert f'name="{field}"' in details, field
        assert f'name="{field}"' not in outside, field


def returns_disclosure_open_when_a_filter_is_set_and_closed_when_none() -> None:
    plant_clinic()

    closed = re.search(r"<details[^>]*>", _root())
    opened = re.search(r"<details[^>]*>", _root("?window=7_days"))
    text_only = re.search(r"<details[^>]*>", _root("?q=Ada"))

    assert closed is not None and opened is not None and text_only is not None
    assert "open" not in closed.group(0).split()
    assert "open" in opened.group(0).split()
    assert "open" not in text_only.group(0).split()


def returns_results_when_form_is_submitted_as_a_browser_does_with_fields_in_the_disclosure() -> (
    None
):
    from scheduling.views.pages.browser_support import SITE_ORIGIN, browser_client

    clinician, _ = plant_clinic()
    form, _, _ = _form_parts(_root())
    pairs = {"q": "Ada", "city": "Berlin", "window": "7_days", "sort": "name_asc"}
    for name in re.findall(r'<(?:input|select)[^>]*\bname="([^"]+)"', form):
        assert (
            name in pairs
            or name in MORE_FILTER_FIELDS
            or name in {"list", "page_size", "latitude", "longitude"}
        ), name

    response = browser_client().get("/", pairs, headers={"Origin": SITE_ORIGIN})

    assert response.status_code == 200
    assert "Ada Lovelace" in response.content.decode()


def returns_q_field_in_its_own_main_row_in_the_stylesheet() -> None:
    from pathlib import Path

    css = (Path(__file__).resolve().parents[3] / "static" / "css" / "components.css").read_text()

    assert ".search-form__main" in css
    assert re.search(r"\.more-filters[^{]*\{[^}]*align-items: end", css)
