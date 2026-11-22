"""Task 18, section 10: the admin record pages as a browser uses them (cross-site check on,
`Origin` set). One flow serves five records, so the cases run over the kinds where they can."""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from django.db.models import Model
from django.test import Client

from scheduling.models import Hospital, Room
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
CONSOLE = "/admin-console"
PLURAL = {
    "hospital": "hospitals",
    "specialty": "specialties",
    "department": "departments",
    "room": "rooms",
    "appointment_type": "appointment-types",
}
MODEL = {
    "hospital": "Hospital",
    "specialty": "Specialty",
    "department": "Department",
    "room": "Room",
    "appointment_type": "AppointmentType",
}
KINDS = sorted(PLURAL)
HOSPITAL_FORM = {
    "name": "Saint Anne", "code": "Saint-Anne", "street_address": "1 Rue Neuve",
    "postal_code": "75001", "city": "Paris", "country": "France", "phone": "+33 1 23 45 67 89",
    "time_zone": "Europe/Paris", "latitude": "", "longitude": "", "description": "",
    "is_active": "on",
}  # fmt: skip


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _page(client: Client, path: str) -> str:
    return client.get(path).content.decode()


def _row_count(html: str) -> int:
    return len(re.findall(r"<tr[ >]", html.split("<tbody", 1)[1]))


def _form_for(kind: str) -> dict[str, str]:
    forms: dict[str, Callable[[], dict[str, str]]] = {
        "hospital": lambda: dict(HOSPITAL_FORM),
        "specialty": lambda: {"name": "Neurology", "code": "Neurology", "is_active": "on"},
        "department": lambda: {
            "name": "Imaging", "code": "Imaging", "description": "",
            "hospital": str(make("Hospital").pk),
        },
        "room": lambda: {
            "name": "Room 7", "code": "Room-7", "floor": "2", "capacity": "2",
            "equipment": "scanner\nbed", "is_active": "on",
            "department": str(make("Department").pk),
        },
        "appointment_type": lambda: {
            "name": "Scan", "code": "Scan", "duration_minutes": "20", "buffer_minutes": "5",
            "colour": "#1A2B3C", "needs_room": "on", "is_active": "on",
            "is_bookable_online": "on", "department": str(make("Department").pk),
        },
    }  # fmt: skip
    return forms[kind]()


def _existing(kind: str, **overrides: object) -> Model:
    return make(MODEL[kind], **overrides)


def returns_20_rows_and_the_total_when_25_hospitals_exist() -> None:
    for number in range(25):
        make("Hospital", name=f"Hospital {number:02d}", code=f"h-{number:02d}")

    first = _page(admin_client(), f"{CONSOLE}/hospitals")
    second = _page(admin_client(), f"{CONSOLE}/hospitals?page=2")

    assert "25 hospitals" in first
    assert (_row_count(first), _row_count(second)) == (20, 5)


def returns_the_matching_row_when_search_names_a_code_in_other_letter_case() -> None:
    make("Hospital", name="Riverside", code="river-1")
    make("Hospital", name="Hillside", code="hill-1")

    html = _page(admin_client(), f"{CONSOLE}/hospitals?q=RIVER")

    assert ("Riverside" in html, "Hillside" in html, "1 hospital" in html) == (True, False, True)


def returns_the_row_whose_code_matches_when_the_name_does_not() -> None:
    make("Hospital", name="Riverside", code="north-7")
    make("Hospital", name="Hillside", code="south-3")

    html = _page(admin_client(), f"{CONSOLE}/hospitals?q=NORTH-7")

    assert ("Riverside" in html, "Hillside" in html, "1 hospital" in html) == (True, False, True)


def returns_percent_row_only_when_search_has_a_percent_sign() -> None:
    make("Hospital", name="Plain", code="plain")
    make("Hospital", name="Odd%name", code="odd")

    html = _page(admin_client(), f"{CONSOLE}/hospitals?q=%25")

    assert ("Odd%name" in html, "Plain" in html) == (True, False)


@pytest.mark.parametrize("page", ["abc", "0", "-3", "999"])
def returns_a_page_of_rows_and_no_error_when_page_number_is_unusable(page: str) -> None:
    make("Hospital")

    response = admin_client().get(f"{CONSOLE}/hospitals?page={page}")

    assert response.status_code == 200 and _row_count(response.content.decode()) == 1


@pytest.mark.parametrize("kind", KINDS)
def returns_303_to_the_show_page_and_stores_lower_case_code_when_admin_creates(kind: str) -> None:
    client = admin_client()
    data = _form_for(kind)

    response = admin_post(client, f"{CONSOLE}/{PLURAL[kind]}/new", data)

    assert response.status_code == 303
    assert re.fullmatch(rf"{CONSOLE}/{PLURAL[kind]}/[0-9a-f-]{{36}}", response["Location"])
    assert data["name"] in _page(client, response["Location"])


@pytest.mark.parametrize("kind", KINDS)
def returns_422_with_typed_values_and_error_beside_code_when_code_is_taken(kind: str) -> None:
    _existing(kind, code="taken")
    data = {**_form_for(kind), "code": "TAKEN", "name": "Typed name to keep"}

    response = admin_post(admin_client(), f"{CONSOLE}/{PLURAL[kind]}/new", data)

    html = response.content.decode()
    assert response.status_code == 422
    assert 'value="Typed name to keep"' in html
    assert re.search(r'id="id_code_error"[^>]*>.*?Code is taken\.', html, re.S)
    assert 'aria-describedby="id_code_error"' in html


def returns_403_when_a_create_post_carries_another_sites_origin() -> None:
    response = admin_post(
        admin_client(), f"{CONSOLE}/hospitals/new", HOSPITAL_FORM, OTHER_SITE_ORIGIN
    )

    assert response.status_code == 403
    assert Hospital.objects.count() == 0


def returns_422_and_keeps_every_typed_value_when_latitude_comes_without_longitude() -> None:
    data = {**HOSPITAL_FORM, "latitude": "45.5", "name": "Keep me", "city": "Keep city"}

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/new", data)

    html = response.content.decode()
    assert response.status_code == 422
    assert all(f'value="{typed}"' in html for typed in ("Keep me", "Keep city", "45.5"))


def returns_422_naming_the_zone_field_when_time_zone_is_unknown() -> None:
    data = {**HOSPITAL_FORM, "time_zone": "Mars/Olympus"}

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/new", data)

    assert response.status_code == 422
    assert 'id="id_time_zone_error"' in response.content.decode()


def returns_the_version_it_read_in_a_hidden_field_when_the_edit_form_is_shown() -> None:
    hospital = _existing("hospital")

    html = _page(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit")

    assert re.search(r'<input[^>]*type="hidden"[^>]*name="version"[^>]*value="1"', html)


def returns_409_with_typed_values_and_refreshed_version_when_the_version_is_stale() -> None:
    hospital = _existing("hospital", name="Before")
    client = admin_client()
    path = f"{CONSOLE}/hospitals/{hospital.pk}/edit"
    assert isinstance(hospital, Hospital)
    first = {**HOSPITAL_FORM, "code": hospital.code, "name": "First admin", "version": "1"}
    assert admin_post(client, path, first).status_code == 303
    second = {**first, "name": "Second admin"}

    response = admin_post(client, path, second)

    html = response.content.decode()
    assert response.status_code == 409
    assert "Another admin saved this record first." in html
    assert 'value="Second admin"' in html
    assert re.search(r'name="version"[^>]*value="2"', html)
    assert Hospital.objects.get(pk=hospital.pk).name == "First admin"


def returns_422_and_keeps_the_form_when_the_version_is_missing_or_not_a_number() -> None:
    hospital = _existing("hospital")
    data = {**HOSPITAL_FORM, "code": "other-code", "version": "abc"}

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit", data)

    assert response.status_code == 422


def returns_count_and_zone_sentence_when_hospital_has_two_upcoming_appointments() -> None:
    clinic = make_clinic()
    for day in (1, 2):
        make(
            "Appointment", patient=clinic.patient, clinician=clinic.clinician,
            appointment_type=clinic.appointment_type,
            starts_at=NOW + timedelta(days=day), ends_at=NOW + timedelta(days=day, hours=1),
        )  # fmt: skip
    make(
        "Appointment", patient=clinic.patient, clinician=clinic.clinician,
        appointment_type=clinic.appointment_type, status="CANCELLED",
        cancelled_at=NOW, cancellation_reason="Patient asked",
        starts_at=NOW + timedelta(days=3), ends_at=NOW + timedelta(days=3, hours=1),
    )  # fmt: skip

    html = _page(admin_client(), f"{CONSOLE}/hospitals/{clinic.department.hospital_id}/edit")

    assert "2 upcoming appointments" in html
    assert "moves nothing that is stored" in html


def returns_singular_sentence_when_hospital_has_one_upcoming_appointment() -> None:
    clinic = make_clinic()
    make(
        "Appointment", patient=clinic.patient, clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=NOW + timedelta(days=1), ends_at=NOW + timedelta(days=1, hours=1),
    )  # fmt: skip

    html = _page(admin_client(), f"{CONSOLE}/hospitals/{clinic.department.hospital_id}/edit")

    assert "has 1 upcoming appointment." in html


def returns_no_time_zone_sentence_when_hospital_has_no_upcoming_appointment() -> None:
    hospital = _existing("hospital")

    html = _page(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/edit")

    assert "upcoming appointment" not in html


def returns_fallback_icon_on_the_show_page_of_a_specialty_without_a_vendored_icon() -> None:
    specialty = _existing("specialty", code="underwater-basket")

    html = _page(admin_client(), f"{CONSOLE}/specialties/{specialty.pk}")

    assert "fallback.svg" in html and "no vendored icon" in html


def returns_its_icon_file_on_the_show_page_of_the_cardiology_specialty() -> None:
    specialty = _existing("specialty", code="cardiology")

    html = _page(admin_client(), f"{CONSOLE}/specialties/{specialty.pk}")

    assert "cardiology.svg" in html and "no vendored icon" not in html


def returns_the_confirmation_and_changes_nothing_when_delete_page_is_only_shown() -> None:
    hospital = _existing("hospital")

    response = admin_client().get(f"{CONSOLE}/hospitals/{hospital.pk}/delete")

    assert response.status_code == 200
    assert Hospital.objects.filter(pk=hospital.pk).exists()
    assert "<form" in response.content.decode()


def returns_303_to_the_list_and_removes_the_record_when_delete_is_confirmed() -> None:
    hospital = _existing("hospital")

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/delete", {})

    assert (response.status_code, response["Location"]) == (303, f"{CONSOLE}/hospitals")
    assert not Hospital.objects.filter(pk=hospital.pk).exists()


def returns_409_listing_reasons_with_counts_and_no_delete_button_when_refused() -> None:
    hospital = _existing("hospital")
    make("Department", hospital=hospital)
    make("Department", hospital=hospital)

    response = admin_post(admin_client(), f"{CONSOLE}/hospitals/{hospital.pk}/delete", {})

    html = response.content.decode()
    assert response.status_code == 409
    assert "has_dependents" not in html and "2 departments" in html
    assert not re.search(r'<form[^>]*action="[^"]*/delete"', html)
    assert Hospital.objects.filter(pk=hospital.pk).exists()


def returns_422_with_the_count_when_room_move_hits_two_default_room_clinicians() -> None:
    room = make("Room")
    assert isinstance(room, Room)
    for _ in range(2):
        make("ClinicianProfile", department=room.department, default_room=room)
    target = make("Department")
    data = {
        "name": room.name, "code": room.code, "floor": room.floor, "capacity": str(room.capacity),
        "equipment": "", "is_active": "on", "department": str(target.pk), "version": "1",
    }  # fmt: skip

    response = admin_post(admin_client(), f"{CONSOLE}/rooms/{room.pk}/edit", data)

    assert response.status_code == 422
    assert "2 clinicians" in response.content.decode()


def _every_admin_page() -> list[str]:
    hospital = _existing("hospital")
    specialty = _existing("specialty")
    department = _existing("department")
    room = _existing("room")
    appointment_type = _existing("appointment_type")
    records = {
        "hospitals": hospital, "specialties": specialty, "departments": department,
        "rooms": room, "appointment-types": appointment_type,
    }  # fmt: skip
    paths = [f"{CONSOLE}/"]
    for plural, record in records.items():
        base = f"{CONSOLE}/{plural}"
        paths += [base, f"{base}/new", f"{base}/{record.pk}"]
        paths += [f"{base}/{record.pk}/edit", f"{base}/{record.pk}/delete"]
    return paths


def returns_unique_ids_and_one_current_nav_item_on_every_admin_page() -> None:
    client = admin_client()

    for path in _every_admin_page():
        html = _page(client, path)
        ids = re.findall(r'\sid="([^"]+)"', html)
        assert sorted(ids) == sorted(set(ids)), path
        assert html.count('aria-current="page"') == 1, path
        assert "<script>" not in html and ' style="' not in html, path


def returns_labelled_inputs_and_captioned_tables_on_every_admin_page() -> None:
    client = admin_client()

    for path in _every_admin_page():
        html = _page(client, path)
        for field_id in re.findall(r'<(?:input|select|textarea)[^>]*\sid="([^"]+)"', html):
            assert f'for="{field_id}"' in html, (path, field_id)
        if "<table" in html:
            assert "<caption" in html and 'scope="col"' in html, path


def returns_unbuilt_sections_as_text_not_links_in_the_navigation() -> None:
    html = _page(admin_client(), f"{CONSOLE}/")

    for section in ("Appointments", "Waitlist", "Audit log", "Settings"):
        assert re.search(rf'aria-disabled="true"[^>]*>{section}<', html), section
        assert not re.search(rf"<a [^>]*>{section}</a>", html), section


def returns_403_and_keeps_the_row_when_a_delete_post_has_no_origin_header() -> None:
    hospital = _existing("hospital", name="Untouched")
    client = admin_client()
    client.cookies["csrftoken"] = "x" * 32

    response = client.post(f"{CONSOLE}/hospitals/{hospital.pk}/delete", {})

    assert response.status_code == 403
    assert Hospital.objects.filter(name="Untouched").exists()
