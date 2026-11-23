"""Hostile page-form values (spec §4): every field of every post form a page renders, found by the
walk and not by a fixed list of names, gets each hostile value, and none answers 500."""

from __future__ import annotations

import pytest

from scheduling.views.pages.browser_support import SITE_ORIGIN
from scheduling.views.pages.form_walk_support import PageForm, post_forms
from scheduling.views.pages.page_walk_support import (
    ROLES,
    World,
    client_for_role,
    make_world,
    page_routes,
    path_of,
)

pytestmark = pytest.mark.django_db

# Measured counts: 126 forms and 325 fields over 100 page answers. A floor, not a target:
# a walk that goes blind fails here instead of passing with nothing sent.
MINIMUM_WALKED_FORMS = 126
MINIMUM_WALKED_FIELDS = 325

HOSTILE_VALUES = (
    "a\x00b",
    "x" * 20_000,
    str(2**64),
    "-1",
    "<script>alert(1)</script>",
)
CLINICIAN_APPOINTMENT_ROUTE = "clinician/appointments/<uuid:appointment_id>"
Statuses = dict[tuple[str, str, str], int]


def _page_statuses(role: str, world: World, path: str) -> Statuses:
    client = client_for_role(role, world)
    client.raise_request_exception = False
    response = client.get(path)
    if response.status_code != 200:
        return {}
    statuses: Statuses = {}
    for form in post_forms(response.content.decode(), path):
        for name in form.values:
            for value in HOSTILE_VALUES:
                posted = client.post(
                    form.action, {**form.values, name: value}, headers={"Origin": SITE_ORIGIN}
                )
                statuses[(form.action, name, value)] = posted.status_code
    return statuses


def _server_errors(statuses: Statuses) -> list[str]:
    return [
        f"{action} {name} {value[:20]!r} -> {status}"
        for (action, name, value), status in statuses.items()
        if status >= 500
    ]


def returns_clinical_notes_sent_and_no_500_when_the_clinician_appointment_page_is_walked() -> None:
    world = make_world()
    path = path_of(CLINICIAN_APPOINTMENT_ROUTE, world)
    statuses = _page_statuses("clinician", world, path)
    names_sent = {name for (_, name, _) in statuses}
    assert "clinical_notes" in names_sent
    assert _server_errors(statuses) == []


def returns_at_least_the_measured_forms_and_fields_when_every_page_is_walked() -> None:
    world = make_world()
    forms: list[PageForm] = []
    for route in page_routes():
        path = path_of(route, world)
        for role in ROLES:
            response = client_for_role(role, world).get(path)
            if response.status_code == 200:
                forms.extend(post_forms(response.content.decode(), path))
    fields = sum(len(form.values) for form in forms)

    assert len(forms) >= MINIMUM_WALKED_FORMS
    assert fields >= MINIMUM_WALKED_FIELDS


@pytest.mark.parametrize("route", page_routes())
def returns_no_500_when_every_page_form_field_gets_hostile_value_as_each_role(route: str) -> None:
    world = make_world()
    path = path_of(route, world)
    failures: list[str] = []
    for role in ROLES:
        failures.extend(
            f"{role} {path} {line}" for line in _server_errors(_page_statuses(role, world, path))
        )
    assert failures == []
