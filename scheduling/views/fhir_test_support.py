"""Shared pieces of the task 23 FHIR tests: a bearer-token client, a frozen clock, JSON writes."""

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django.test import Client

from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.models.builders import make_user
from scheduling.use_cases.api_tokens import issue_token
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
FHIR_JSON = "application/fhir+json"
BASE = "https://drlibre.example/fhir"


def token_of(user: User | None = None, role: Role | str = "ADMIN") -> str:
    with bind_request_context(RequestContext("test-token", clock.now_utc())):
        return issue_token(user or make_user(role=role), "Task 23").token


def client_for(token: str | None) -> Client:
    """A FHIR client: bearer token, no cookie, no Origin, cross-site check enforced."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return Client(enforce_csrf_checks=True, raise_request_exception=False, headers=headers)


def get(path: str, token: str | None = None) -> "_MonkeyPatchedWSGIResponse":
    return client_for(token).get(path)


def send(
    method: str, path: str, body: object, token: str | None, **headers: str
) -> "_MonkeyPatchedWSGIResponse":
    client = client_for(token)
    call = {"post": client.post, "put": client.put, "delete": client.delete}[method]
    return call(path, data=json.dumps(body), content_type=FHIR_JSON, headers=headers)


def extension(url_name: str, **value: object) -> dict[str, object]:
    return {"url": f"{BASE}/StructureDefinition/{url_name}", **value}


def schedule_body(
    clinician_user_id: object,
    weekday: int = 2,
    start: str = "10:00:00",
    end: str = "11:00:00",
    step: int = 30,
    horizon_start: str = "2030-01-07",
) -> dict[str, object]:
    return {
        "resourceType": "Schedule",
        "active": True,
        "actor": [{"reference": f"Practitioner/{clinician_user_id}"}],
        "planningHorizon": {"start": horizon_start},
        "extension": [
            extension("schedule-weekday", valueInteger=weekday),
            extension("schedule-start-time", valueTime=start),
            extension("schedule-end-time", valueTime=end),
            extension("schedule-slot-step-minutes", valueInteger=step),
        ],
    }
