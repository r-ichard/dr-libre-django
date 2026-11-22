"""Task 19, section 10: the user and clinician pages as a browser uses them (cross-site check
on, `Origin` set), the deactivation step, the read-only calendar and the password page."""

import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from scheduling.models import AuditLogEntry, ClinicianProfile, Session, User
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages.admin_support import (
    admin_client,
    admin_post,
    client_of_role,
)
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
CONSOLE = "/admin-console"
PLANTED = "Pl4nted-Secret-9x"
NEW_USER = {
    "full_name": "Ada Planted",
    "email": "Ada.Planted@Example.org",
    "role": "CLINICIAN",
    "password": PLANTED,
}


@pytest.fixture(autouse=True)
def returns_frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _profile() -> ClinicianProfile:
    row = make("ClinicianProfile")
    assert isinstance(row, ClinicianProfile)
    return row


def _user(**overrides: object) -> User:
    row = make("User", **overrides)
    assert isinstance(row, User)
    return row


def returns_303_and_no_password_in_any_page_or_log_when_an_admin_creates_a_user(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    client = admin_client()

    response = admin_post(client, f"{CONSOLE}/users/new", NEW_USER)
    followed = client.get(response["Location"]).content.decode()

    assert response.status_code == 303
    created = User.objects.get(email="ada.planted@example.org")
    assert response["Location"] == f"{CONSOLE}/users/{created.pk}"
    assert PLANTED not in followed and created.password not in followed
    assert PLANTED not in caplog.text
    assert PLANTED not in str(list(AuditLogEntry.objects.values_list("metadata", flat=True)))


def returns_422_with_typed_values_and_an_empty_password_when_the_form_is_refused() -> None:
    response = admin_post(
        admin_client(), f"{CONSOLE}/users/new", {**NEW_USER, "email": "not-an-address"}
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert "Ada Planted" in html and PLANTED not in html
    assert re.search(
        r'id="id_password"[^>]*type="password"|type="password"[^>]*id="id_password"', html
    )
    assert 'id="id_email_error"' in html and 'autocomplete="new-password"' in html


def returns_403_when_a_user_form_is_posted_from_another_site() -> None:
    response = admin_post(
        admin_client(), f"{CONSOLE}/users/new", NEW_USER, origin=OTHER_SITE_ORIGIN
    )

    assert response.status_code == 403
    assert not User.objects.filter(email="ada.planted@example.org").exists()


def returns_20_rows_the_total_and_a_match_in_any_letter_case_when_users_are_listed() -> None:
    for number in range(25):
        _user(full_name=f"Listed Person {number:02d}", email=f"listed{number:02d}@example.org")
    client = admin_client()

    first = client.get(f"{CONSOLE}/users").content.decode()
    search = client.get(f"{CONSOLE}/users?q=LISTED07@EXAMPLE").content.decode()

    assert len(re.findall(r"<tr[ >]", first.split("<tbody", 1)[1])) == 20
    assert "26 users" in first
    assert "Listed Person 07" in search and "Listed Person 08" not in search


def returns_no_password_hash_on_the_show_page_of_a_user() -> None:
    target = _user()

    html = admin_client().get(f"{CONSOLE}/users/{target.pk}").content.decode()

    assert target.password not in html and target.email in html


def returns_no_role_select_and_no_deactivate_link_when_an_admin_edits_the_own_account() -> None:
    client = admin_client()
    own = User.objects.get(role="ADMIN")

    form = client.get(f"{CONSOLE}/users/{own.pk}/edit").content.decode()
    show = client.get(f"{CONSOLE}/users/{own.pk}").content.decode()

    assert 'name="role"' not in form and "/deactivate" not in show


def returns_confirmation_with_upcoming_count_then_signs_the_clinician_out() -> None:
    profile = _profile()
    target = User.objects.get(clinicianprofile__pk=profile.pk)
    make(
        "Appointment",
        clinician=profile,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=15),
    )
    signed_in = client_of_role("CLINICIAN")
    other = User.objects.exclude(pk=target.pk).get(role="CLINICIAN")
    admin = admin_client()
    path = f"{CONSOLE}/users/{target.pk}/deactivate"

    page = admin.get(path).content.decode()
    response = admin_post(admin, path, {"version": str(target.version)})

    assert "1 upcoming appointment" in page and "They stay booked" in page
    assert response.status_code == 303
    target.refresh_from_db()
    assert not target.is_active and not Session.objects.filter(user=target).exists()
    assert other.is_active and signed_in.get("/clinician/").status_code != 500


def returns_409_and_ends_no_session_when_the_deactivation_form_is_stale() -> None:
    target = _user(role="PATIENT")
    admin = admin_client()
    stale = str(target.version + 5)

    response = admin_post(admin, f"{CONSOLE}/users/{target.pk}/deactivate", {"version": stale})

    assert response.status_code == 409
    target.refresh_from_db()
    assert target.is_active


def returns_refusal_with_advice_to_deactivate_when_the_user_has_appointments() -> None:
    patient = _user(role="PATIENT")
    make("Appointment", patient=patient)
    admin = admin_client()

    response = admin_post(admin, f"{CONSOLE}/users/{patient.pk}/delete", {})

    html = response.content.decode()
    assert response.status_code == 409
    assert "1 appointment as a patient" in html and "Deactivate instead" in html
    assert User.objects.filter(pk=patient.pk).exists()


def returns_form_without_the_user_select_and_303_when_a_profile_is_edited() -> None:
    profile = _profile()
    admin = admin_client()
    path = f"{CONSOLE}/clinicians/{profile.pk}/edit"

    form = admin.get(path).content.decode()
    values = {
        "department": str(profile.department_id),
        "specialty": str(profile.specialty_id),
        "title": "Professor",
        "bio": "",
        "default_room": "",
        "round_robin_weight": "2",
        "version": str(profile.version),
    }
    response = admin_post(admin, path, values)

    assert 'name="user"' not in form and 'name="round_robin_weight"' in form
    assert response.status_code == 303
    assert ClinicianProfile.objects.get(pk=profile.pk).title == "Professor"


def returns_422_when_a_clinician_profile_has_a_weight_of_zero() -> None:
    clinician = _user()
    department = make("Department")
    specialty = make("Specialty")
    values = {
        "user": str(clinician.pk), "department": str(department.pk),
        "specialty": str(specialty.pk), "title": "Dr", "bio": "", "default_room": "",
        "round_robin_weight": "0",
    }  # fmt: skip

    response = admin_post(admin_client(), f"{CONSOLE}/clinicians/new", values)

    assert response.status_code == 422 and not ClinicianProfile.objects.exists()


def returns_list_with_department_specialty_status_and_availability_summary() -> None:
    profile = _profile()
    make("AvailabilityRule", clinician=profile, weekday=1)

    html = admin_client().get(f"{CONSOLE}/clinicians").content.decode()

    assert profile.department.name in html and profile.specialty.name in html
    assert "Active" in html and "Mon 09:00–17:00" in html


def returns_read_only_week_with_navigation_and_no_link_or_note_when_the_calendar_is_shown() -> None:
    profile = _profile()
    patient = _user(role="PATIENT", full_name="Pat Visible")
    day = datetime(2030, 1, 8, 10, 0, tzinfo=UTC)
    appointment = make(
        "Appointment",
        clinician=profile,
        patient=patient,
        starts_at=day,
        ends_at=day + timedelta(minutes=15),
    )
    make("ClinicalNote", appointment=appointment, clinical_notes="planted-clinical-note")
    path = f"{CONSOLE}/clinicians/{profile.pk}/calendar"

    html = admin_client().get(f"{path}?week=2030-01-07").content.decode()

    assert "Previous week" in html and "Next week" in html
    assert f"{path}?week=2029-12-31" in html and f"{path}?week=2030-01-14" in html
    assert "planted-clinical-note" not in html and "<form" not in html.split("<main", 1)[-1]
    assert "/clinician/appointments/" not in html and "Pat Visible" in html


def returns_404_when_the_calendar_names_no_profile() -> None:
    path = f"{CONSOLE}/clinicians/6f1c3a52-0d1e-4b8a-9c53-2f7d1b0e4a11/calendar"

    assert admin_client().get(path).status_code == 404


@pytest.mark.parametrize("role", ["CLINICIAN", "ADMIN"])
def returns_303_and_ends_other_sessions_when_the_temporary_password_is_replaced(role: str) -> None:
    client: Client = client_of_role(role)
    user = User.objects.get(role=role)
    user.set_password(PLANTED)
    user.save()
    elsewhere = Session.objects.filter(user=user).count()

    path = "/account/password"
    wrong = admin_post(client, path, {"current_password": "x" * 12, "new_password": "n" * 12})
    changed = {"current_password": PLANTED, "new_password": "another-Password-1"}
    right = admin_post(client, path, changed)

    assert wrong.status_code == 422 and right.status_code == 303 and elsewhere == 1
    user.refresh_from_db()
    assert user.check_password("another-Password-1")


def returns_403_when_a_patient_opens_the_account_password_page() -> None:
    assert client_of_role("PATIENT").get("/account/password").status_code == 403
