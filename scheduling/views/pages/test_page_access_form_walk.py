"""Form-only pages, posted as a browser posts them, by each caller: the answer is the row's, or the
product's where a pair is listed. Also held: sign-out ends the session, the export is a CSV
attachment, and a POST from another site is refused."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from django.http.response import HttpResponseBase
from django.test import Client

from scheduling.models import Notification
from scheduling.views.pages.browser_support import (
    CSRF_COOKIE,
    OTHER_SITE_ORIGIN,
    SITE_ORIGIN,
    browser_client,
)
from scheduling.views.pages.form_walk_support import PageForm, post_forms
from scheduling.views.pages.page_walk_support import World, client_for_role, make_world
from scheduling.views.pages.test_page_access_rows import Answer, Caller
from scheduling.views.pages.test_page_access_table import _all_rows
from scheduling.views.pages.test_page_access_walk import (
    CALLERS,
    _answer_of,
    _wanted,
)
from scheduling.views.session_cookie import SESSION_COOKIE

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

pytestmark = pytest.mark.django_db

SIGN_OUT = "sign-out"
EMAIL_LINK = "sign-in/email-link"
READ_ALL = "patient/notifications/read-all"
REMINDERS = "admin-console/settings/reminders"
EXPORT = "admin-console/appointments/export"

# The page each form is on. A signed-in caller who opens /sign-in is sent to the home, which
# holds the sign-out form, so one page serves every caller.
FORM_PAGES = {
    SIGN_OUT: "/sign-in",
    EMAIL_LINK: "/sign-in",
    READ_ALL: "/patient/notifications",
    REMINDERS: "/admin-console/settings",
    EXPORT: "/admin-console/appointments",
}
HOME_OF_ROLE = {
    "patient": "/patient/",
    "clinician": "/clinician/",
    "admin": "/admin-console/",
}
ATTACHMENT_NAME = r'attachment; filename="appointments-\d{4}-\d{2}-\d{2}\.csv"'


def _browser_clients(world: World) -> dict[Caller, Client]:
    return {
        "visitor": browser_client(),
        "patient": client_for_role("patient", world),
        "clinician": client_for_role("clinician", world),
        "admin": client_for_role("admin", world),
    }


def _typed_fields(route: str, caller: Caller) -> dict[str, str]:
    """What a caller types. Each caller types its own address: no address gets a second request."""
    if route == EMAIL_LINK:
        return {"link_email": f"{caller}@walk.example.test"}
    return {}


def _form_values(forms: list[PageForm], route: str) -> dict[str, str]:
    for form in forms:
        if urlsplit(form.action).path == f"/{route}":
            return form.values
    return {}


def _post_form(
    client: Client, route: str, typed: dict[str, str], origin: str = SITE_ORIGIN
) -> _MonkeyPatchedWSGIResponse:
    """Opens the form's page as a browser does, takes the form's named fields as they came, adds
    what the caller typed, and posts with the cross-site cookie that page set."""
    page = FORM_PAGES[route]
    rendered = client.get(page, follow=True)
    values = _form_values(post_forms(rendered.content.decode(), page), route)
    token = client.cookies[CSRF_COOKIE].value
    data = {**values, **typed, "csrfmiddlewaretoken": token}
    return client.post(f"/{route}", data, headers={"Origin": origin})


def _answer_as_sent(response: HttpResponseBase, wanted: str) -> str:
    """A product redirect, such as "302 /sign-in", is compared as sent: _answer_of maps every
    sign-in path to SIGN_IN and would hide the difference. A table answer uses _answer_of."""
    if " " in wanted:
        return f"{response.status_code} {response.headers.get('Location', '')}"
    return _answer_of(response)


def returns_expected_answer_when_caller_posts_form_route() -> None:
    world = make_world()
    shared = _browser_clients(world)
    rows = {row.route: row for row in _all_rows()}
    mismatches: list[str] = []
    for route in FORM_PAGES:
        # Sign-out ends the caller's session, so it gets its own signed-in clients.
        clients = _browser_clients(world) if route == SIGN_OUT else shared
        for caller in CALLERS:
            want = _wanted(rows[route], caller)
            response = _post_form(clients[caller], route, _typed_fields(route, caller))
            got = _answer_as_sent(response, want)
            if got != want:
                mismatches.append(f"{caller} {route}: want {want} got {got}")
    assert mismatches == [], "\n".join(mismatches)


@pytest.mark.parametrize("role", list(HOME_OF_ROLE))
def returns_sign_in_when_home_asked_with_session_token_after_sign_out(role: str) -> None:
    world = make_world()
    client = client_for_role(role, world)
    home = HOME_OF_ROLE[role]
    stale = Client()
    stale.cookies[SESSION_COOKIE] = client.cookies[SESSION_COOKIE].value
    # The token opens the home before sign-out, so a sign-in answer afterwards is sign-out's doing.
    assert _answer_of(stale.get(home)) == Answer.OK
    _post_form(client, SIGN_OUT, {})
    assert _answer_of(stale.get(home)) == Answer.SIGN_IN


def returns_csv_attachment_when_admin_posts_export() -> None:
    client = client_for_role("admin", make_world())
    response = _post_form(client, EXPORT, {})
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert re.fullmatch(ATTACHMENT_NAME, response.headers["Content-Disposition"])


def returns_403_when_form_posted_from_other_site() -> None:
    world = make_world()
    client = client_for_role("patient", world)
    response = _post_form(client, READ_ALL, {}, origin=OTHER_SITE_ORIGIN)
    assert response.status_code == 403
    unread = Notification.objects.filter(recipient=world.clinic.patient, read_at__isnull=True)
    assert unread.exists()
