"""Section 10: what an admin action did, said once on the page the admin lands on. The cookie is
signed but readable in the browser, so it carries a code and an id; the sentence, with any name
in it, is written at render."""

from uuid import UUID

from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.views.pages.notice_sentences import notice_sentence

ADMIN_NOTICE_COOKIE = "drlibre_admin_notice"
NOTICE_LIFETIME_SECONDS = 60
NOTICE_SALT = "admin-notice"


def admin_redirect(
    path: str, code: str, subject: UUID | None = None, kind: str = ""
) -> HttpResponseRedirect:
    response = HttpResponseRedirect(path, status=303)
    response.set_cookie(
        ADMIN_NOTICE_COOKIE,
        signing.dumps(
            {"code": code, "subject": str(subject or ""), "kind": kind}, salt=NOTICE_SALT
        ),
        max_age=NOTICE_LIFETIME_SECONDS,
        httponly=True,
        samesite="Strict",
    )
    return response


def take_admin_notice(request: HttpRequest) -> str:
    """The sentence for a cookie we signed and that is still fresh; anything else is no notice."""
    raw = request.COOKIES.get(ADMIN_NOTICE_COOKIE, "")
    try:
        payload = signing.loads(raw, salt=NOTICE_SALT, max_age=NOTICE_LIFETIME_SECONDS)
    except signing.BadSignature:
        return ""
    if not isinstance(payload, dict):
        return ""
    return notice_sentence(
        str(payload.get("code")), str(payload.get("subject")), str(payload.get("kind"))
    )


def forget_admin_notice(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    if ADMIN_NOTICE_COOKIE in request.COOKIES:
        response.delete_cookie(ADMIN_NOTICE_COOKIE, samesite="Strict")
    return response
