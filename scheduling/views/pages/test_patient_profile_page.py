"""Section 8: the profile and change-password pages, as a browser sends them."""

from __future__ import annotations

import re
from datetime import date

import pytest
from django.contrib.auth.hashers import make_password

from scheduling.models import Session, User
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import (
    NOW,
    PHRASE,
    no_inline_code,
    signed_in_patient,
)
from scheduling.views.pages.browser_support import OTHER_SITE_ORIGIN, browser_post

pytestmark = pytest.mark.django_db

PROFILE = "/patient/profile"
PASSWORD = "/patient/profile/password"  # noqa: S105 - a page path, not a secret
NEW_PHRASE = "a different long phrase"


def _parts(day: str, month: str, year: str) -> dict[str, str]:
    return {"date_of_birth_day": day, "date_of_birth_month": month, "date_of_birth_year": year}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _patient(**fields: object) -> User:
    fields = {"full_name": "Pat Example", "email": "pat.profile@example.test", **fields}
    patient = make("User", **fields)
    assert isinstance(patient, User)
    return patient


def returns_name_and_email_as_text_and_phone_and_birth_date_as_inputs() -> None:
    patient = _patient(phone="+33 1 23 45 67", date_of_birth=date(1990, 2, 3))

    html = signed_in_patient(patient).get(PROFILE).content.decode()

    assert "Pat Example" in html
    assert "pat.profile@example.test" in html
    assert 'name="email"' not in html
    assert 'name="full_name"' not in html
    assert 'value="+33 1 23 45 67"' in html
    assert re.search(r'id="id_date_of_birth_year"[^>]*value="1990"', html)
    assert no_inline_code(html)


def returns_303_and_saved_values_when_profile_is_posted_as_a_browser_sends_it() -> None:
    patient = _patient()
    form = {"phone": "+33 1 23 45 67", **_parts("3", "2", "1990")}

    response = browser_post(signed_in_patient(patient), PROFILE, form)

    patient.refresh_from_db()
    assert response.status_code == 303
    assert patient.phone == "+33 1 23 45 67"
    assert patient.date_of_birth == date(1990, 2, 3)


def returns_cleared_values_when_profile_is_posted_empty() -> None:
    patient = _patient(phone="+33 1 23 45 67", date_of_birth=date(1990, 2, 3))

    browser_post(signed_in_patient(patient), PROFILE, {"phone": "", **_parts("", "", "")})

    patient.refresh_from_db()
    assert patient.phone == ""
    assert patient.date_of_birth is None


@pytest.mark.parametrize(
    ("form", "field"),
    [
        ({"phone": "12ab", **_parts("", "", "")}, "phone"),
        ({"phone": "", **_parts("1", "1", "2999")}, "date_of_birth"),
        ({"phone": "", **_parts("30", "2", "2031")}, "date_of_birth"),
    ],
)
def returns_422_with_summary_and_kept_values_when_profile_input_is_bad(
    form: dict[str, str], field: str
) -> None:
    patient = _patient()

    response = browser_post(signed_in_patient(patient), PROFILE, form)

    html = response.content.decode()
    assert response.status_code == 422
    assert "There is a problem" in html
    assert f'id="id_{field}_error"' in html


def returns_403_when_profile_comes_from_another_site() -> None:
    patient = _patient()

    response = browser_post(
        signed_in_patient(patient), PROFILE, {"phone": "1234567"}, OTHER_SITE_ORIGIN
    )

    patient.refresh_from_db()
    assert response.status_code == 403
    assert patient.phone == ""


def returns_password_link_only_when_patient_has_a_usable_password() -> None:
    patient = _patient()
    passwordless = _patient(email="pat.passwordless@example.test")

    assert PASSWORD in signed_in_patient(patient).get(PROFILE).content.decode()
    client = signed_in_patient(passwordless)
    passwordless.refresh_from_db()
    passwordless.set_unusable_password()
    passwordless.email_verified_at = NOW
    passwordless.save()

    assert PASSWORD not in client.get(PROFILE).content.decode()


def returns_404_on_get_and_post_when_patient_has_no_password() -> None:
    patient = _patient()
    client = signed_in_patient(patient)
    patient.refresh_from_db()
    patient.set_unusable_password()
    patient.email_verified_at = NOW
    patient.save()

    assert client.get(PASSWORD).status_code == 404
    posted = browser_post(client, PASSWORD, {"current_password": "x", "new_password": NEW_PHRASE})
    assert posted.status_code == 404


def returns_password_inputs_that_are_typed_and_never_filled() -> None:
    html = signed_in_patient(_patient()).get(PASSWORD).content.decode()

    assert html.count('type="password"') == 2
    assert 'autocomplete="current-password"' in html
    assert 'autocomplete="new-password"' in html


def returns_303_and_ends_other_sessions_when_password_is_changed() -> None:
    patient = _patient()
    other = signed_in_patient(patient)
    this = signed_in_patient(patient)

    response = browser_post(
        this, PASSWORD, {"current_password": PHRASE, "new_password": NEW_PHRASE}
    )

    patient.refresh_from_db()
    assert response.status_code == 303
    assert patient.check_password(NEW_PHRASE)
    assert other.get(PROFILE).status_code == 302
    assert this.get(PROFILE).status_code == 200
    assert Session.objects.filter(user=patient).count() == 1


def returns_422_and_empty_fields_when_current_password_is_wrong() -> None:
    patient = _patient()

    response = browser_post(
        signed_in_patient(patient),
        PASSWORD,
        {"current_password": "wrong", "new_password": NEW_PHRASE},
    )

    html = response.content.decode()
    assert response.status_code == 422
    assert "The current password is not right." in html
    assert "wrong" not in html.replace("is not right", "")
    assert NEW_PHRASE not in html


def returns_422_when_new_password_is_too_short() -> None:
    response = browser_post(
        signed_in_patient(_patient()),
        PASSWORD,
        {"current_password": PHRASE, "new_password": "short"},
    )

    assert response.status_code == 422
    assert "Use 10 to 72 characters." in response.content.decode()


def returns_403_when_password_form_comes_from_another_site() -> None:
    patient = _patient()
    form = {"current_password": PHRASE, "new_password": NEW_PHRASE}

    response = browser_post(signed_in_patient(patient), PASSWORD, form, OTHER_SITE_ORIGIN)

    patient.refresh_from_db()
    assert response.status_code == 403
    assert patient.password != make_password(NEW_PHRASE)
    assert patient.check_password(PHRASE)
