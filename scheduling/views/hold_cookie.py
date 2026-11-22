"""Task 26a item 6: the code page belongs to the browser that made the hold. The cookie is proof of
that browser only, never an identity: the mailed code is still needed to book."""

import hmac
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils.http import http_date

from scheduling.views.session_cookie import SAME_SITE

HOLD_COOKIE = "drlibre_hold"


ENTRY_SEPARATOR = "."
PROOF_CHARACTERS = 32
# Eight entries are 534 characters, far under the 4096 a browser keeps; the oldest drop first, and a
# hold lives ten minutes, so a browser with more open at once is not a visitor.
MAXIMUM_ENTRIES = 8


def _proof(hold_id: UUID) -> str:
    key = settings.SECRET_KEY.encode()
    digest = hmac.new(key, f"hold-browser:{hold_id}".encode(), "sha256").hexdigest()
    return digest[:PROOF_CHARACTERS]


def _entry(hold_id: UUID) -> str:
    return f"{hold_id.hex}-{_proof(hold_id)}"


def set_hold_cookie(
    request: HttpRequest, response: HttpResponseBase, hold_id: UUID, expires_at: datetime
) -> None:
    earlier = request.COOKIES.get(HOLD_COOKIE, "").split(ENTRY_SEPARATOR)
    kept = [entry for entry in earlier if entry and entry != _entry(hold_id)]
    entries = [*kept, _entry(hold_id)][-MAXIMUM_ENTRIES:]
    response.set_cookie(
        HOLD_COOKIE,
        ENTRY_SEPARATOR.join(entries),
        expires=http_date(expires_at.timestamp()),
        httponly=True,
        samesite=SAME_SITE,
        secure=settings.HTTPS_ONLY,
        path="/",
    )


def made_this_hold(request: HttpRequest, hold_id: UUID) -> bool:
    wanted = _entry(hold_id).encode()
    presented = request.COOKIES.get(HOLD_COOKIE, "").split(ENTRY_SEPARATOR)
    return any(hmac.compare_digest(entry.encode(), wanted) for entry in presented)
