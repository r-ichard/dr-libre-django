"""Section 10: what an admin action did, said once on the page the admin lands on. The sentence
is built by the server after the write and rides a short-lived signed cookie, so nothing in the
address or the form can write it."""

from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

ADMIN_NOTICE_COOKIE = "drlibre_admin_notice"
NOTICE_LIFETIME_SECONDS = 60
NOTICE_SALT = "admin-notice"


def admin_redirect(path: str, sentence: str) -> HttpResponseRedirect:
    response = HttpResponseRedirect(path, status=303)
    response.set_cookie(
        ADMIN_NOTICE_COOKIE,
        signing.dumps(sentence, salt=NOTICE_SALT),
        max_age=NOTICE_LIFETIME_SECONDS,
        httponly=True,
        samesite="Strict",
    )
    return response


def take_admin_notice(request: HttpRequest) -> str:
    """The sentence of a cookie we signed and that is still fresh; anything else is no notice."""
    raw = request.COOKIES.get(ADMIN_NOTICE_COOKIE, "")
    try:
        sentence = signing.loads(raw, salt=NOTICE_SALT, max_age=NOTICE_LIFETIME_SECONDS)
    except signing.BadSignature:
        return ""
    return sentence if isinstance(sentence, str) else ""


def forget_admin_notice(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    if ADMIN_NOTICE_COOKIE in request.COOKIES:
        response.delete_cookie(ADMIN_NOTICE_COOKIE, samesite="Strict")
    return response
