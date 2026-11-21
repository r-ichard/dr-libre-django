"""Section 12: page forms refuse a cross-site POST and accept the site's own, as a browser sends
them (task 13a). `Origin: null` is what a browser sends after `Referrer-Policy: no-referrer`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.hashers import make_password

from scheduling.models import SignInLink
from scheduling.models.builders import make
from scheduling.use_cases.session import hash_token
from scheduling.views.pages.browser_support import (
    NULL_ORIGIN,
    OTHER_SITE_ORIGIN,
    SITE_ORIGIN,
    browser_client,
    browser_post,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

EMAIL = "pat.browser@example.test"
PASSWORD = "correct horse battery staple"  # noqa: S105 - a planted test value
TOKEN = "browser-token-abcdefghijklmnopqrstuvwxyz"  # noqa: S105 - a planted test value
REFUSED_ORIGINS = [NULL_ORIGIN, OTHER_SITE_ORIGIN]

FORMS = {
    "continue": ("/sign-in/link", {"token": TOKEN}, 303),
    "sign_in": ("/sign-in", {"email": EMAIL, "password": PASSWORD}, 302),
    "sign_out": ("/sign-out", {}, 302),
    "link_request": ("/sign-in/email-link", {"link_email": EMAIL}, 303),
}


@pytest.fixture(autouse=True)
def stored_patient_and_link() -> None:
    patient = make("User", email=EMAIL, role="PATIENT", password=make_password(PASSWORD))
    make(
        "SignInLink",
        token_hash=hash_token(TOKEN),
        patient=patient,
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
        expires_at=datetime(2999, 1, 1, tzinfo=UTC),
    )


def _post(name: str, origin: str) -> _MonkeyPatchedWSGIResponse:
    path, data, _ = FORMS[name]
    return browser_post(browser_client(), path, data, origin)


@pytest.mark.parametrize("name", FORMS)
def returns_redirect_when_form_is_posted_with_the_site_origin(name: str) -> None:
    response = _post(name, SITE_ORIGIN)

    assert response.status_code == FORMS[name][2]


@pytest.mark.parametrize("origin", REFUSED_ORIGINS)
@pytest.mark.parametrize("name", FORMS)
def returns_403_when_form_is_posted_with_null_or_other_site_origin(name: str, origin: str) -> None:
    response = _post(name, origin)

    assert response.status_code == 403


@pytest.mark.parametrize("origin", REFUSED_ORIGINS)
def returns_link_unused_when_continue_is_posted_with_null_or_other_site_origin(
    origin: str,
) -> None:
    _post("continue", origin)

    assert SignInLink.objects.get().used_at is None


@pytest.mark.parametrize("debug", [True, False])
def returns_product_403_page_with_correlation_id_when_csrf_check_fails(
    settings: object, debug: bool
) -> None:
    settings.DEBUG = debug  # type: ignore[attr-defined]
    client = browser_client()
    client.get("/sign-in")
    token = client.cookies["csrftoken"].value

    response = client.post(
        "/sign-in/link",
        {"token": TOKEN, "csrfmiddlewaretoken": token},
        headers={"Origin": NULL_ORIGIN, "X-Correlation-Id": "corr-csrf-1"},
    )

    html = response.content.decode()
    assert response.status_code == 403
    assert "You cannot open this page" in html
    assert "corr-csrf-1" in html
    assert "DEBUG" not in html
    assert "template tag" not in html
