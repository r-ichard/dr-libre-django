"""The session cookie: name and attributes only, no policy. Scripts cannot read it, other sites
cannot send it, and outside development it travels over HTTPS only."""

from datetime import datetime
from typing import Literal

from django.conf import settings
from django.utils.http import http_date
from rest_framework.response import Response

SESSION_COOKIE = "drlibre_session"
SAME_SITE: Literal["Strict"] = "Strict"


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    # An explicit expires string: Django would derive max-age from the wall clock.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        expires=http_date(expires_at.timestamp()),
        httponly=True,
        samesite=SAME_SITE,
        secure=settings.HTTPS_ONLY,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", samesite=SAME_SITE)
