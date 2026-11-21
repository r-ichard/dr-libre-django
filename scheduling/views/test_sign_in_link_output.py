"""Section 11: a planted token never reaches a log line, stderr, stdout, an audit entry, a stored
row or an error page, through the page and the API, at the level of what the process writes."""

from __future__ import annotations

import io
import json
import logging
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.test import Client

from scheduling.models import AuditLogEntry, RateLimitHit, SignInLink
from scheduling.models.builders import make
from scheduling.use_cases.session import hash_token
from scheduling.views import clock
from scheduling.views.json_logging import JsonFormatter

pytestmark = pytest.mark.django_db


def _wait_until_idle() -> None:
    """Imported here, so a module not written yet fails its tests and not the collection."""
    from scheduling.use_cases.background_mail import wait_until_idle  # noqa: PLC0415

    wait_until_idle()


PLANTED = "planted-secret-token-0123456789abcdefghijk"
EMAIL = "pat.secret@example.test"
NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


@pytest.fixture
def written() -> Iterator[io.StringIO]:
    """Every log record of the process, formatted by the real JSON formatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    previous = root.level
    root.setLevel(logging.DEBUG)
    yield stream
    root.removeHandler(handler)
    root.setLevel(previous)


def _everything_stored() -> str:
    rows = [
        list(SignInLink.objects.values()),
        list(AuditLogEntry.objects.values("action", "entity_id", "metadata")),
        list(RateLimitHit.objects.values()),
    ]
    return json.dumps(rows, default=str)


def returns_no_token_in_output_rows_or_pages_when_link_goes_through_ask_page_and_use(
    written: io.StringIO,
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    settings: object,
    django_capture_on_commit_callbacks: object,
) -> None:
    monkeypatch.setattr(secrets, "token_urlsafe", lambda _size=None: PLANTED)
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {
            "BACKEND": "scheduling.use_cases.test_sign_in_link_support.MailServerDownBackend",
            "OPTIONS": {},
        }
    }
    make("User", email=EMAIL)
    client = Client(raise_request_exception=False)
    bodies: list[str] = []

    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        bodies.append(
            client.post(
                "/api/v1/auth/link", {"email": EMAIL}, content_type="application/json"
            ).content.decode()
        )
    _wait_until_idle()
    bodies.append(client.get(f"/sign-in/link?token={PLANTED}").content.decode())
    bodies.append(client.post("/sign-in/link", {"token": PLANTED}).content.decode())
    bodies.append(
        client.post(
            "/api/v1/auth/link/verify", {"token": PLANTED}, content_type="application/json"
        ).content.decode()
    )
    bodies.append(client.post("/sign-in/link", {"token": PLANTED}).content.decode())

    process_output = capfd.readouterr()
    assert PLANTED not in written.getvalue()
    assert PLANTED not in process_output.out + process_output.err
    assert PLANTED not in _everything_stored()
    assert all(PLANTED not in body for body in bodies)
    assert SignInLink.objects.get().token_hash == hash_token(PLANTED)


def returns_no_token_in_output_or_rows_when_page_and_api_refuse_a_planted_token(
    written: io.StringIO, capfd: pytest.CaptureFixture[str]
) -> None:
    client = Client(raise_request_exception=False)

    page = client.post("/sign-in/link", {"token": PLANTED})
    api = client.post(
        "/api/v1/auth/link/verify", {"token": PLANTED}, content_type="application/json"
    )

    captured = capfd.readouterr()
    assert (page.status_code, api.status_code) == (400, 400)
    assert PLANTED not in written.getvalue() + captured.out + captured.err + _everything_stored()
    assert PLANTED not in page.content.decode() + api.content.decode()
