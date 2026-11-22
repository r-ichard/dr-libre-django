"""Task 22, spec 15.4: API tokens are issued, resolved and revoked; only a hash is stored, every
step is audited with ids only, and failed attempts are limited."""

import logging
from collections.abc import Iterator
from datetime import timedelta

import pytest
from django.db import connection

from scheduling.domain.failure import Failure, Success
from scheduling.models import ApiClient, AuditLogEntry
from scheduling.models.builders import make_user
from scheduling.use_cases.api_tokens import (
    issue_token,
    list_tokens,
    resolve_token,
    revoke_token,
)
from scheduling.use_cases.test_booking_support import ADDRESS, NOW, _at

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def returns_user_when_token_is_valid() -> None:
    user = make_user(role="CLINICIAN")
    issued = issue_token(user, "Reporting")

    answer = resolve_token(issued.token, ADDRESS)

    assert isinstance(answer, Success)
    assert answer.value.pk == user.pk


def returns_only_the_hash_when_token_is_stored() -> None:
    issued = issue_token(make_user(), "Reporting")

    with connection.cursor() as cursor:
        cursor.execute("SELECT row_to_json(t)::text FROM scheduling_apiclient t")
        stored = cursor.fetchall()

    assert issued.token not in str(stored)
    assert ApiClient.objects.get().token_hash != issued.token


@pytest.mark.parametrize("state", ["unknown", "revoked", "inactive"])
def returns_unauthenticated_when_token_is_unknown_revoked_or_user_inactive(state: str) -> None:
    user = make_user(is_active=state != "inactive")
    issued = issue_token(user, "Reporting")
    if state == "revoked":
        revoke_token(issued.client.pk)
    presented = "dlk_unknown" if state == "unknown" else issued.token

    assert resolve_token(presented, ADDRESS) == Failure.unauthenticated()


def returns_rate_limited_when_one_token_failed_five_times_in_an_hour() -> None:
    answers = [resolve_token("dlk_wrong", f"198.51.100.{number}") for number in range(6)]

    assert answers[:5] == [Failure.unauthenticated()] * 5
    assert answers[5] == Failure.rate_limited()


def returns_rate_limited_when_one_address_failed_twenty_times_in_an_hour() -> None:
    answers = [resolve_token(f"dlk_wrong{number}", ADDRESS) for number in range(21)]

    assert answers[19] == Failure.unauthenticated()
    assert answers[20] == Failure.rate_limited()


def returns_user_when_good_token_follows_failures_and_is_not_counted() -> None:
    issued = issue_token(make_user(), "Reporting")
    for _ in range(4):
        resolve_token("dlk_wrong", ADDRESS)

    answers = [resolve_token(issued.token, ADDRESS) for _ in range(10)]

    assert all(isinstance(answer, Success) for answer in answers)


def returns_unauthenticated_when_the_hour_has_passed_after_limit() -> None:
    for _ in range(6):
        resolve_token("dlk_wrong", ADDRESS)

    with _at(NOW + timedelta(minutes=61)):
        assert resolve_token("dlk_wrong", ADDRESS) == Failure.unauthenticated()


def returns_audit_entries_with_ids_only_when_token_issued_and_revoked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = make_user(full_name="Planted Name")
    with caplog.at_level(logging.DEBUG):
        issued = issue_token(user, "Planted Service")
        with _at(NOW + timedelta(seconds=1)):
            revoke_token(issued.client.pk)
        list_tokens()

    entries = list(AuditLogEntry.objects.order_by("created_at", "id"))
    assert sorted(entry.action for entry in entries) == ["api_client.issue", "api_client.revoke"]
    assert all(entry.entity_id == str(issued.client.pk) for entry in entries)
    assert all(entry.metadata["ids"] == {"user_id": str(user.pk)} for entry in entries)
    everything = str([entry.metadata for entry in entries]) + caplog.text
    assert issued.token not in everything
    assert "Planted Service" not in everything


def returns_listing_without_hash_or_token_when_tokens_are_listed() -> None:
    issued = issue_token(make_user(), "Reporting")

    listed = list_tokens()

    assert [row.pk for row in listed] == [issued.client.pk]
    assert issued.token not in repr(listed)


def returns_not_found_when_revoking_an_unknown_token() -> None:
    assert revoke_token(make_user().pk) == Failure.not_found()
