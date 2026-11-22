"""Task 26a2 items 6 and 7: one browser that makes two holds in two tabs completes both. The cookie
proves every hold its browser made that has not expired, stays HttpOnly and stays small."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from django.core import mail
from django.test import Client

from scheduling.models import Appointment
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages import booking_code
from scheduling.views.pages.booking_pages_support import FORM, NOW, details_path
from scheduling.views.pages.browser_support import browser_client, browser_post

pytestmark = pytest.mark.django_db

HOLD_COOKIE = "drlibre_hold"
MAXIMUM_COOKIE_CHARACTERS = 600
HOLDS_PER_BROWSER = 8
UNKNOWN_HOLD_PATH = "/book/holds/00000000-0000-4000-8000-000000000000/code"


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    instant = [NOW]
    monkeypatch.setattr(clock, "now_utc", lambda: instant[0])
    return instant


def _hold(client: Client, number: int) -> str:
    form = {**FORM, "email": f"tab.{number}@example.test"}
    return browser_post(client, details_path(make_clinic()), form)["Location"]


def _code_mailed_to(number: int) -> str:
    recipient = f"tab.{number}@example.test"
    body = next(str(sent.body) for sent in reversed(mail.outbox) if recipient in sent.to)
    found = re.search(r"\b(\d{6})\b", body)
    assert found is not None  # noqa: S101 - a missing code is a broken setup
    return found.group(1)


def _without_reference(content: bytes) -> str:
    return re.sub(r"<code>[0-9a-f]{32}</code>", "", content.decode())


def returns_both_code_pages_when_two_holds_are_made_in_one_browser(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    first = _hold(client, 1)
    second = _hold(client, 2)

    statuses = [client.get(first).status_code, client.get(second).status_code]

    assert statuses == [200, 200]


def returns_two_appointments_when_both_tabs_enter_their_mailed_code(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    first = _hold(client, 1)
    second = _hold(client, 2)

    outcomes = [
        browser_post(client, first, {"code": _code_mailed_to(1)}).status_code,
        browser_post(client, second, {"code": _code_mailed_to(2)}).status_code,
    ]

    assert outcomes == [303, 303]
    assert Appointment.objects.count() == 2


def returns_missing_hold_page_when_another_browser_opens_either_code_page(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    first = _hold(client, 1)
    second = _hold(client, 2)
    missing = browser_client().get(UNKNOWN_HOLD_PATH)

    answers = [browser_client().get(path) for path in (first, second)]

    assert [(answer.status_code, _without_reference(answer.content)) for answer in answers] == [
        (missing.status_code, _without_reference(missing.content))
    ] * 2


def returns_short_http_only_cookie_when_eight_holds_are_made(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    for number in range(HOLDS_PER_BROWSER):
        _hold(client, number)

    morsel = client.cookies[HOLD_COOKIE]

    assert morsel["httponly"]
    assert len(morsel.value) <= MAXIMUM_COOKIE_CHARACTERS


def returns_expired_hold_page_when_the_first_hold_is_older_than_its_lifetime(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    first = _hold(client, 1)
    frozen_clock[0] = NOW + timedelta(minutes=11)
    _hold(client, 2)

    assert len(client.cookies[HOLD_COOKIE].value) < MAXIMUM_COOKIE_CHARACTERS
    assert client.get(first).status_code == browser_client().get(first).status_code


def returns_missing_hold_page_before_reading_hold_when_resend_has_no_cookie(
    frozen_clock: list[datetime], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = browser_client()
    code_path = _hold(client, 1)

    def fail_if_read(_hold_id: object) -> None:
        raise AssertionError("the hold was read before the cookie was checked")

    monkeypatch.setattr(booking_code, "hold_summary", fail_if_read)
    response = browser_post(browser_client(), code_path.replace("/code", "/resend"), {})

    assert response.status_code == 404


def returns_cookie_within_size_cap_and_newest_holds_when_twelve_holds_are_made(
    frozen_clock: list[datetime],
) -> None:
    client = browser_client()
    paths = [_hold(client, number) for number in range(12)]

    assert len(client.cookies[HOLD_COOKIE].value) <= MAXIMUM_COOKIE_CHARACTERS
    assert client.get(paths[-1]).status_code == 200
    assert client.get(paths[0]).status_code != 200


def returns_one_entry_when_the_same_hold_sets_the_cookie_twice() -> None:
    from uuid import uuid4

    from django.http import HttpResponse
    from django.test import RequestFactory

    from scheduling.views.hold_cookie import set_hold_cookie

    hold_id = uuid4()
    first = HttpResponse()
    set_hold_cookie(RequestFactory().get("/"), first, hold_id, NOW)
    request = RequestFactory().get("/")
    request.COOKIES[HOLD_COOKIE] = first.cookies[HOLD_COOKIE].value
    second = HttpResponse()

    set_hold_cookie(request, second, hold_id, NOW)

    assert second.cookies[HOLD_COOKIE].value == first.cookies[HOLD_COOKIE].value
