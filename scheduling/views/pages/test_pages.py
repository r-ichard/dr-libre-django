"""Task 05a: sign-in screen, role homes, sign-out, error pages, layout, style page."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory

from scheduling.models import Session
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages import errors

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

SIGN_IN = "/sign-in"
SIGN_OUT = "/sign-out"
PHRASE = "correct horse battery staple"
START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
HOME_PATH = {"PATIENT": "/patient/", "CLINICIAN": "/clinician/", "ADMIN": "/admin-console/"}
ROLES = list(HOME_PATH)
WRONG_MESSAGE = "Email or password is not correct."


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: START)


def _make_user(role: str, email: str = "jane@example.test", name: str = "Jane Doe") -> None:
    make("User", email=email, role=role, full_name=name, password=make_password(PHRASE))


def _signed_in_client(role: str) -> Client:
    _make_user(role)
    client = Client()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "jane@example.test", "password": PHRASE},
        content_type="application/json",
    )
    assert login.status_code == 200
    return client


def _form_post(
    client: Client, email: str, password: str, **extra: str
) -> _MonkeyPatchedWSGIResponse:
    return client.post(SIGN_IN, {"email": email, "password": password, **extra})


def returns_form_with_labelled_fields_and_one_heading_when_sign_in_is_requested() -> None:
    response = Client().get(SIGN_IN)

    html = response.content.decode()
    assert response.status_code == 200
    assert len(re.findall(r"<h1[ >]", html)) == 1
    for field in ("email", "password"):
        assert re.search(rf'<input[^>]*id="id_{field}"', html)
        assert re.search(rf'<label[^>]*for="id_{field}"', html)


@pytest.mark.parametrize("role", ROLES)
def returns_redirect_to_role_home_and_cookie_when_credentials_are_right(role: str) -> None:
    _make_user(role)

    response = _form_post(Client(), "jane@example.test", PHRASE)

    assert response.status_code == 302
    assert response["Location"] == HOME_PATH[role]
    assert response.cookies["drlibre_session"]["httponly"] is True


def returns_redirect_to_next_when_next_is_local() -> None:
    _make_user("CLINICIAN")

    response = _form_post(Client(), "jane@example.test", PHRASE, next="/clinician/")

    assert response["Location"] == "/clinician/"


def returns_role_home_when_next_is_external() -> None:
    _make_user("PATIENT")

    response = _form_post(Client(), "jane@example.test", PHRASE, next="https://evil.test/")

    assert response["Location"] == "/patient/"


def returns_same_message_when_email_is_unknown_and_when_password_is_wrong() -> None:
    _make_user("PATIENT")

    unknown = _form_post(Client(), "nobody@example.test", PHRASE)
    wrong = _form_post(Client(), "jane@example.test", "not the phrase")

    assert unknown.status_code == wrong.status_code == 200
    assert WRONG_MESSAGE in unknown.content.decode()
    assert WRONG_MESSAGE in wrong.content.decode()


def returns_lockout_message_when_ten_failures_in_window() -> None:
    _make_user("PATIENT")
    for _ in range(10):
        _form_post(Client(), "jane@example.test", "not the phrase")

    response = _form_post(Client(), "jane@example.test", PHRASE)

    html = response.content.decode()
    assert response.status_code == 200
    assert "try again in 15 minutes" in html.lower()
    assert WRONG_MESSAGE not in html


def returns_no_password_in_response_when_sign_in_fails() -> None:
    response = _form_post(Client(), "jane@example.test", "hunter2-secret")

    assert "hunter2-secret" not in response.content.decode()


def returns_field_errors_tied_to_fields_when_fields_are_empty() -> None:
    response = _form_post(Client(), "", "")

    html = response.content.decode()
    for field in ("email", "password"):
        described = re.search(rf'<input[^>]*id="id_{field}"[^>]*aria-describedby="([^"]+)"', html)
        assert described, field
        for target in described.group(1).split():
            assert f'id="{target}"' in html
        assert re.search(rf'<input[^>]*id="id_{field}"[^>]*aria-invalid="true"', html)


def returns_only_first_invalid_field_marked_for_focus_when_errors() -> None:
    response = _form_post(Client(), "", "")

    html = response.content.decode()
    assert html.count("data-autofocus") == 1
    assert re.search(r'<input[^>]*id="id_email"[^>]*data-autofocus', html)


def returns_403_when_csrf_token_is_missing() -> None:
    client = Client(enforce_csrf_checks=True)

    response = client.post(SIGN_IN, {"email": "a@example.test", "password": "x"})

    assert response.status_code == 403


def returns_redirect_to_home_when_already_signed_in() -> None:
    client = _signed_in_client("CLINICIAN")

    response = client.get(SIGN_IN)

    assert response.status_code == 302
    assert response["Location"] == "/clinician/"


@pytest.mark.parametrize("path", HOME_PATH.values())
def returns_redirect_to_sign_in_with_next_when_anonymous(path: str) -> None:
    response = Client().get(path)

    assert response.status_code == 302
    assert response["Location"] == f"{SIGN_IN}?next={path}"


@pytest.mark.parametrize("role", ROLES)
def returns_greeting_with_user_name_when_role_matches(role: str) -> None:
    client = _signed_in_client(role)

    response = client.get(HOME_PATH[role])

    assert response.status_code == 200
    assert "Hello, Jane Doe" in response.content.decode()


@pytest.mark.parametrize(
    ("role", "other"),
    [(role, other) for role in ROLES for other in ROLES if role != other],
)
def returns_forbidden_page_when_role_differs(role: str, other: str) -> None:
    client = _signed_in_client(role)

    response = client.get(HOME_PATH[other])

    assert response.status_code == 403
    assert "Hello, Jane Doe" not in response.content.decode()


def returns_redirect_to_sign_in_when_user_is_deactivated() -> None:
    client = _signed_in_client("PATIENT")
    user = Session.objects.get().user
    user.is_active = False
    user.save()

    response = client.get(HOME_PATH["PATIENT"])

    assert response.status_code == 302
    assert response["Location"].startswith(SIGN_IN)


def returns_405_when_sign_out_is_a_get() -> None:
    assert Client().get(SIGN_OUT).status_code == 405


def returns_redirect_and_ends_session_when_sign_out_is_posted() -> None:
    client = _signed_in_client("PATIENT")

    response = client.post(SIGN_OUT)

    assert response.status_code == 302
    assert response["Location"] == SIGN_IN
    assert Session.objects.count() == 0
    assert client.get(HOME_PATH["PATIENT"]).status_code == 302


def returns_403_when_sign_out_csrf_token_is_missing() -> None:
    assert Client(enforce_csrf_checks=True).post(SIGN_OUT).status_code == 403


def returns_product_name_and_sign_in_link_when_root_is_requested() -> None:
    response = Client().get("/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "DrLibre" in html
    assert f'href="{SIGN_IN}"' in html


def returns_language_main_and_skip_link_when_any_page_is_rendered() -> None:
    html = Client().get(SIGN_IN).content.decode()

    assert re.search(r'<html[^>]*lang="en"', html)
    assert len(re.findall(r"<main[ >]", html)) == 1
    target = re.search(r'<a[^>]*class="skip-link"[^>]*href="#([^"]+)"', html)
    assert target
    assert re.search(rf'<main[^>]*id="{target.group(1)}"', html)


def returns_sign_out_form_and_name_in_header_only_when_signed_in() -> None:
    anonymous = Client().get("/").content.decode()
    signed_in = _signed_in_client("PATIENT").get(HOME_PATH["PATIENT"]).content.decode()

    assert SIGN_OUT not in anonymous
    assert re.search(rf'<form[^>]*method="post"[^>]*action="{SIGN_OUT}"', signed_in)
    assert "csrfmiddlewaretoken" in signed_in


@pytest.mark.parametrize("path", ["/", SIGN_IN])
def returns_no_inline_script_or_style_when_page_is_rendered(path: str) -> None:
    html = Client().get(path).content.decode()

    assert not re.search(r"<style|\sstyle=|\son\w+=|<script(?![^>]*\ssrc=)", html)


def returns_css_when_static_file_is_requested(settings: object) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]

    response = Client().get("/static/css/tokens.css")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/css")


def returns_404_page_with_correlation_id_when_path_is_unknown(settings: object) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]

    response = Client().get("/pages/unknown", headers={"X-Correlation-Id": "abc-123"})

    assert response.status_code == 404
    assert "abc-123" in response.content.decode()
    assert "<h1" in response.content.decode()


def returns_json_404_when_api_path_is_unknown() -> None:
    response = Client().get("/api/v1/unknown")

    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")


def returns_404_when_style_page_is_requested_and_debug_is_off(settings: object) -> None:
    settings.DEBUG = False  # type: ignore[attr-defined]

    assert Client().get("/style").status_code == 404


def returns_next_path_when_next_is_local_and_differs_from_role_home() -> None:
    _make_user("PATIENT")

    target = "/patient/appointments?page=2"

    response = _form_post(Client(), "jane@example.test", PHRASE, next=target)

    assert response["Location"] == target


def returns_focus_on_password_only_when_email_is_filled_and_password_is_empty() -> None:
    html = _form_post(Client(), "jane@example.test", "").content.decode()

    assert html.count("data-autofocus") == 1
    assert re.search(r'<input[^>]*id="id_password"[^>]*data-autofocus', html)


def returns_focus_on_email_when_credentials_are_wrong() -> None:
    _make_user("PATIENT")

    html = _form_post(Client(), "jane@example.test", "not the phrase").content.decode()

    assert html.count("data-autofocus") == 1
    assert re.search(r'<input[^>]*id="id_email"[^>]*data-autofocus', html)


def returns_redirect_when_email_has_surrounding_spaces() -> None:
    _make_user("PATIENT")

    response = _form_post(Client(), "  jane@example.test  ", PHRASE)

    assert response.status_code == 302


def returns_wrong_message_when_only_another_email_is_locked_out() -> None:
    _make_user("PATIENT")
    for _ in range(10):
        _form_post(Client(), "other@example.test", "not the phrase")

    html = _form_post(Client(), "jane@example.test", "not the phrase").content.decode()

    assert WRONG_MESSAGE in html


def returns_no_store_header_when_sign_in_is_requested() -> None:
    assert "no-store" in Client().get(SIGN_IN)["Cache-Control"]


def returns_cleared_session_cookie_when_sign_out_is_posted() -> None:
    client = _signed_in_client("PATIENT")

    cookie = client.post(SIGN_OUT).cookies["drlibre_session"]

    assert cookie.value == ""
    assert cookie["max-age"] == 0


def returns_403_and_500_pages_with_heading_when_handlers_are_called() -> None:
    request = RequestFactory().get("/anything")

    forbidden = errors.forbidden_page(request, PermissionDenied())
    broken = errors.server_error_page(request)

    assert (forbidden.status_code, broken.status_code) == (403, 500)
    for response in (forbidden, broken):
        assert "<h1" in response.content.decode()


def returns_summary_links_to_each_invalid_field_when_fields_are_empty() -> None:
    html = _form_post(Client(), "", "").content.decode()

    for field in ("email", "password"):
        assert f'href="#id_{field}"' in html
