"""Task 22, spec 15.4: the token command shows the token once and never again."""

import logging
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from scheduling.models import ApiClient, AuditLogEntry
from scheduling.models.builders import make

pytestmark = pytest.mark.django_db


def _run(*arguments: str) -> str:
    output = StringIO()
    call_command("api_tokens", *arguments, stdout=output)
    return output.getvalue()


def returns_token_once_when_issued_and_never_in_later_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = make("User", email="owner@example.test")
    with caplog.at_level(logging.DEBUG):
        token = _run("issue", "Owner@Example.test", "--name", "Planted Service").strip()
        listing = _run("list")
        client_id = str(ApiClient.objects.get().pk)
        revoked = _run("revoke", client_id)

    assert token.startswith("dlk_")
    assert client_id in listing
    assert f"user={user.pk}" in listing
    audit = str(list(AuditLogEntry.objects.values_list("metadata", "entity_id")))
    for later in (listing, revoked, audit, caplog.text, ApiClient.objects.get().token_hash):
        assert token not in later
    assert "revoked" in _run("list")
    assert ApiClient.objects.get().token_hash not in listing


def returns_error_when_user_is_unknown_or_inactive() -> None:
    make("User", email="gone@example.test", is_active=False)

    for email in ("nobody@example.test", "gone@example.test"):
        with pytest.raises(CommandError):
            _run("issue", email, "--name", "Reporting")


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def returns_error_when_name_is_empty_or_too_long(name: str) -> None:
    make("User", email="owner@example.test")

    with pytest.raises(CommandError):
        _run("issue", "owner@example.test", "--name", name)


@pytest.mark.parametrize("raw_id", ["nope", "00000000-0000-0000-0000-000000000000"])
def returns_error_when_revoking_an_unknown_token(raw_id: str) -> None:
    with pytest.raises(CommandError):
        _run("revoke", raw_id)
