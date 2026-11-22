"""Task 17c, #28: an id is unique on every page the product renders. Each page route needs a
fixture here, so a new page cannot skip the check."""

from __future__ import annotations

import re
from collections import Counter

import pytest

from scheduling.models import User
from scheduling.models.builders import make_clinic
from scheduling.views import clock
from scheduling.views.pages.booking_pages_support import NOW, signed_in_patient
from scheduling.views.pages.browser_support import browser_post
from scheduling.views.pages.page_walk_support import (
    client_for_route,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

ID_PATTERN = re.compile(r"""\sid=["']([^"']*)["']""")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _duplicates(html: str) -> list[str]:
    return [name for name, count in Counter(ID_PATTERN.findall(html)).items() if count > 1]


def returns_no_duplicate_id_when_any_page_renders() -> None:
    world = make_world()
    rendered = 0
    problems: dict[str, list[str]] = {}

    for route in page_routes():
        response = client_for_route(route, world).get(path_of(route, world))
        assert response.status_code < 500, route
        rendered += 1
        duplicates = _duplicates(response.content.decode())
        if duplicates:
            problems[route] = duplicates

    assert rendered > 30
    assert problems == {}


def returns_no_duplicate_id_when_time_off_form_answers_422() -> None:
    clinic = make_clinic()
    user = clinic.clinician.user
    assert isinstance(user, User)
    form = {"starts_at": "", "ends_at": "", "reason": ""}

    response = browser_post(signed_in_patient(user), "/clinician/time-off", form)

    assert response.status_code == 422
    assert _duplicates(response.content.decode()) == []
