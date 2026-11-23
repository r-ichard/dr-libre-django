"""Signed-in clients of the admin page tests, and the form posts of a browser."""

from typing import TYPE_CHECKING

from django.test import Client

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import SessionKind
from scheduling.models import User
from scheduling.models.builders import make
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.views import clock
from scheduling.views.pages.browser_support import (
    CSRF_COOKIE,
    SITE_ORIGIN,
    TOKEN_SOURCE_PATH,
    browser_client,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

SESSION_COOKIE = "drlibre_session"
CONSOLE = "/admin-console"


def client_of_role(role: str) -> Client:
    user = make("User", role=role)
    if not isinstance(user, User):
        raise TypeError("builder returned a different model")
    client = browser_client()
    with bind_request_context(RequestContext(correlation_id="admin-page", now=clock.now_utc())):
        client.cookies[SESSION_COOKIE] = open_session(user, SessionKind.PASSWORD, "").token
    return client


def admin_client() -> Client:
    return client_of_role("ADMIN")


def admin_post(
    client: Client, path: str, data: dict[str, str], origin: str = SITE_ORIGIN
) -> "_MonkeyPatchedWSGIResponse":
    """`browser_post` takes its token from /sign-in, which sends a signed-in admin away without
    one. The token comes from a visitor's request, the form post is the admin's."""
    token = _form_token()
    client.cookies[CSRF_COOKIE] = token
    return client.post(path, {**data, "csrfmiddlewaretoken": token}, headers={"Origin": origin})


def _form_token() -> str:
    visitor = Client()
    visitor.get(TOKEN_SOURCE_PATH)
    return visitor.cookies[CSRF_COOKIE].value
