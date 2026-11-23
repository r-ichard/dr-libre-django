"""Section 16: focus moves to the first invalid control of every form, once, in the shared
component. The script looks for the invalid mark every component sets; the pages mark it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scheduling.models.builders import make_clinic
from scheduling.views.pages.booking_pages_support import signed_in_patient
from scheduling.views.pages.browser_support import browser_post

pytestmark = pytest.mark.django_db

SCRIPT = Path(__file__).resolve().parents[3] / "static" / "js" / "focus_first_error.js"
FORMS = {
    "waitlist": ("/patient/waitlist", {}),
    "password": ("/patient/profile/password", {"current_password": "", "new_password": ""}),
    "profile": ("/patient/profile", {"phone": "abc", "date_of_birth": ""}),
}


def returns_script_that_focuses_the_first_control_marked_invalid() -> None:
    assert 'aria-invalid="true"' in SCRIPT.read_text()


@pytest.mark.parametrize("name", FORMS)
def returns_page_with_invalid_control_marked_and_script_loaded_when_form_is_invalid(
    name: str,
) -> None:
    path, data = FORMS[name]
    client = signed_in_patient(make_clinic().patient)

    response = browser_post(client, path, data)

    html = response.content.decode()
    assert response.status_code == 422
    assert re.search(r'<(input|select)[^>]*aria-invalid="true"', html)
    assert "js/focus_first_error.js" in html
