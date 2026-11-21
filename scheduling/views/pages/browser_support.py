"""Page forms as a browser sends them: cross-site check enforced, Origin header set. The default
test client does neither, so a form can pass every test and still answer 403 in a browser."""

from typing import TYPE_CHECKING

from django.test import Client

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

SITE_ORIGIN = "http://testserver"
OTHER_SITE_ORIGIN = "http://other-site.example"
NULL_ORIGIN = "null"
TOKEN_SOURCE_PATH = "/sign-in"  # noqa: S105 - a page path, not a secret
CSRF_COOKIE = "csrftoken"


def browser_client() -> Client:
    return Client(enforce_csrf_checks=True)


def browser_post(
    client: Client, path: str, data: dict[str, str], origin: str = SITE_ORIGIN
) -> "_MonkeyPatchedWSGIResponse":
    """A page that renders a form hands out the csrf cookie; its value is a valid form token."""
    client.get(TOKEN_SOURCE_PATH)
    token = client.cookies[CSRF_COOKIE].value
    return client.post(path, {**data, "csrfmiddlewaretoken": token}, headers={"Origin": origin})
