"""Task 26b item 2 and 3a: with DEBUG off every cookie the product sets is Secure, HttpOnly and
SameSite, whether HTTPS_ONLY is on or off. Deleting cookies carry an empty value and are skipped:
they hold nothing a script or another site could use."""

from datetime import timedelta
from http.cookies import Morsel

import pytest

from scheduling.models.builders import STARTS_AT, make, make_clinic
from scheduling.views import clock
from scheduling.views.pages.admin_support import admin_client, admin_post
from scheduling.views.pages.booking_pages_support import FORM, NOW, details_path, signed_in_patient
from scheduling.views.pages.browser_support import browser_client, browser_post

pytestmark = pytest.mark.django_db

KNOWN_COOKIES = {
    "drlibre_session",
    "csrftoken",
    "drlibre_hold",
    "drlibre_notice",
    "drlibre_admin_notice",
}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _flow_cookies() -> dict[str, Morsel[str]]:
    clinic = make_clinic()
    signed_out = browser_client()
    browser_post(signed_out, details_path(clinic), {**FORM, "email": "flags@example.test"})
    appointment = make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=STARTS_AT + timedelta(days=7),
        ends_at=STARTS_AT + timedelta(days=7, minutes=30),
    )
    signed_in = signed_in_patient(clinic.patient)
    browser_post(signed_in, f"/patient/appointments/{appointment.pk}/cancel", {"reason": "Cannot"})
    admin = admin_client()
    admin_post(admin, "/admin-console/settings/reminders", {})
    jars = [signed_out.cookies, signed_in.cookies]
    found = {name: jar[name] for jar in jars for name in jar if jar[name].value}
    # admin_post plants its own token cookie by hand, so only the notice the server set counts.
    found["drlibre_admin_notice"] = admin.cookies["drlibre_admin_notice"]
    return found


@pytest.mark.parametrize("https_only", [True, False])
def returns_secure_httponly_samesite_on_every_cookie_when_debug_is_off(
    settings: object, https_only: bool
) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]
    settings.HTTPS_ONLY = https_only  # type: ignore[attr-defined]

    cookies = _flow_cookies()

    assert set(cookies) == KNOWN_COOKIES
    assert set(cookies) <= KNOWN_COOKIES
    for name, cookie in cookies.items():
        assert cookie["secure"] is True, f"{name} is not Secure"
        assert cookie["httponly"] is True, f"{name} is not HttpOnly"
        assert cookie["samesite"] == "Strict", f"{name} is not SameSite=Strict"
