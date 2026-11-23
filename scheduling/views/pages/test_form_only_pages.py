"""A form-only address never leads a browser to a GET that refuses, and a
refused method of a page answers a product page whose Allow header lists what it accepts."""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.urls import URLPattern, URLResolver, get_resolver, resolve

from scheduling.models import User
from scheduling.models.builders import make
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_client, browser_post
from scheduling.views.pages.page_view import PageView

pytestmark = pytest.mark.django_db

READ_ALL_PATH = "/patient/notifications/read-all"
LIST_PATH = "/patient/notifications"
UUID_PLACEHOLDER = re.compile(r"<uuid:\w+>")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


class _ProbePage(PageView):
    http_method_names = ["post"]


class _TemplatePage(PageView):
    template_name = "errors/405.html"


def _patient_client() -> Client:
    patient = make("User")
    assert isinstance(patient, User)
    return signed_in_patient(patient)


def _is_form_only(view_class: type[PageView]) -> bool:
    return view_class.allowed_roles is not None and view_class().is_form_only


def _routes(
    patterns: list[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, object]]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _routes(entry.url_patterns, prefix + str(entry.pattern))
        else:
            yield prefix + str(entry.pattern), entry.callback


def returns_sign_in_next_of_notifications_list_when_anonymous_mark_all_read_is_posted() -> None:
    response = browser_post(browser_client(), READ_ALL_PATH, {})

    assert response.status_code == 302
    assert response["Location"] == f"/sign-in?next={LIST_PATH}"


def returns_405_with_allow_post_and_options_when_signed_in_get_of_mark_all_read() -> None:
    response = _patient_client().get(READ_ALL_PATH)

    assert response.status_code == 405
    assert response["Allow"] == "POST, OPTIONS"


def returns_405_product_page_linking_to_list_when_signed_in_get_of_mark_all_read() -> None:
    response = _patient_client().get(READ_ALL_PATH)

    html = response.content.decode()
    assert "<h1>This address only takes a form</h1>" in html
    assert 'href="/patient/notifications"' in html


def returns_405_not_500_when_signed_in_head_of_mark_all_read() -> None:
    response = _patient_client().head(READ_ALL_PATH)

    assert response.status_code == 405
    assert "HEAD" not in response["Allow"]


def returns_options_allow_without_get_when_asked_for_mark_all_read() -> None:
    response = _patient_client().options(READ_ALL_PATH)

    assert response["Allow"] == "POST, OPTIONS"


def returns_sign_in_next_that_answers_get_for_every_form_only_route() -> None:
    checked: list[str] = []
    for pattern, callback in _routes(get_resolver().url_patterns):
        view_class = getattr(callback, "view_class", None)
        if not (isinstance(view_class, type) and issubclass(view_class, PageView)):
            continue
        if not _is_form_only(view_class):
            continue
        path = UUID_PLACEHOLDER.sub(lambda _match: str(uuid4()), pattern)

        response = Client().get(f"/{path}")

        assert response.status_code == 302, path
        next_path = parse_qs(urlsplit(response["Location"]).query)["next"][0]
        target = getattr(resolve(next_path).func, "view_class")  # noqa: B009 - as_view sets it; stubs omit it
        assert not _is_form_only(target), f"{path} sends next to {next_path}"
        checked.append(path)
    assert len(checked) >= 14, checked


def returns_405_linking_to_code_page_when_get_of_resend_address() -> None:
    hold_id = uuid4()

    response = Client().get(f"/book/holds/{hold_id}/resend")

    html = response.content.decode()
    assert response.status_code == 405
    assert response["Allow"] == "POST"
    assert f'href="/book/holds/{hold_id}/code"' in html


def returns_not_form_only_when_page_renders_a_template() -> None:
    assert _TemplatePage().is_form_only is False


def returns_405_linking_to_start_page_when_form_page_is_not_declared() -> None:
    request: HttpRequest = RequestFactory().get("/probe")

    response = _ProbePage.as_view()(request)
    assert isinstance(response, HttpResponse)

    html = response.content.decode()
    assert response.status_code == 405
    assert '<a href="/">Go to the start page</a>' in html
