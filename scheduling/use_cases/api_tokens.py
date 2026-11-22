"""Spec 15.4: API tokens. A token gives exactly its user's rights and leaves only as the return
value of issue_token; the database holds its SHA-256. Only failed attempts count against the
limit, so a working client is never throttled."""

import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, Result, Success
from scheduling.domain.rate_limit_rules import RateLimitScope
from scheduling.models import ApiClient, User
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.rate_limits import is_full, record_hits
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import TOKEN_BYTES, hash_token

TOKEN_PREFIX = "dlk_"  # noqa: S105 - a public marker, not a secret
LAST_USED_RESOLUTION = timedelta(minutes=1)


@dataclass(frozen=True)
class IssuedToken:
    client: ApiClient
    token: str


def issue_token(user: User, name: str) -> IssuedToken:
    token = TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_BYTES)
    with transaction.atomic():
        client = ApiClient.objects.create(name=name, user=user, token_hash=hash_token(token))
        _audit("api_client.issue", client)
    return IssuedToken(client, token)


def list_tokens() -> list[ApiClient]:
    return list(ApiClient.objects.select_related("user").order_by("created_at", "id"))


def revoke_token(client_id: UUID) -> Result[ApiClient]:
    with transaction.atomic():
        client = ApiClient.objects.select_for_update().filter(pk=client_id).first()
        if client is None:
            return Failure.not_found()
        if client.revoked_at is None:
            client.revoked_at = current_request_context().now
            client.save(update_fields=["revoked_at", "updated_at"])
            _audit("api_client.revoke", client)
    return Success(client)


def resolve_token(token: str, address: str) -> Result[User]:
    """The same failure for an unknown token, a revoked one and an inactive user."""
    token_key = hash_token(token)
    if is_full(RateLimitScope.TOKEN, token_key, address):
        return Failure.rate_limited()
    client = ApiClient.objects.select_related("user").filter(token_hash=token_key).first()
    if client is None or client.revoked_at is not None or not client.user.is_active:
        record_hits(RateLimitScope.TOKEN, token_key, address)
        return Failure.unauthenticated()
    _touch(client)
    return Success(client.user)


def _touch(client: ApiClient) -> None:
    now = current_request_context().now
    if client.last_used_at is None or now - client.last_used_at >= LAST_USED_RESOLUTION:
        ApiClient.objects.filter(pk=client.pk).update(last_used_at=now)


def _audit(action: str, client: ApiClient) -> None:
    metadata = AuditMetadata(ids={"user_id": client.user_id})
    record_audit(AuditEvent(action, "ApiClient", str(client.pk), metadata), None)
