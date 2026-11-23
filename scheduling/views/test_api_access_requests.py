"""The request each route that names no record receives from each caller, sent as the route's real
client sends it: a browser's Origin and cookie, and a body of fields the route accepts."""

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from django.http import HttpResponseBase
from django.test import Client

from scheduling.models.builders import STARTS_AT
from scheduling.views.api_clients import browser_api_client
from scheduling.views.test_api_access_rows import ANY_METHOD, Caller
from scheduling.views.test_api_access_world import PHRASE, TOKEN_BYTES, World, _new_link

Sender = Callable[[World, Caller], HttpResponseBase]
JSON = "application/json"
HOUR = timedelta(hours=1)
UNKNOWN_EMAIL = "nobody@example.test"
WRONG_PHRASE = "wrong horse battery staple"
SLOT_WINDOW = {"from": "2030-01-07T00:00:00Z", "to": "2030-01-08T00:00:00Z"}
WAITLIST_EARLIEST = STARTS_AT.isoformat()
WAITLIST_LATEST = (STARTS_AT + timedelta(days=1)).isoformat()
# The patient, clinician and admin each book a different free slot. The visitor is refused first.
BOOKING_STARTS: dict[Caller, datetime] = {
    Caller.VISITOR: STARTS_AT,
    Caller.PATIENT: STARTS_AT,
    Caller.CLINICIAN: STARTS_AT + HOUR,
    Caller.ADMIN: STARTS_AT + 2 * HOUR,
}


def _client(clients: dict[Caller, Client], caller: Caller) -> Client:
    """A visitor holds no session, so each visitor request is sent from a client of its own."""
    return browser_api_client() if caller is Caller.VISITOR else clients[caller]


def _get(path: str) -> Sender:
    def send(world: World, caller: Caller) -> HttpResponseBase:
        return _client(world.clients, caller).get(path)

    return send


def _login(world: World, caller: Caller) -> HttpResponseBase:
    if caller is Caller.VISITOR:
        body = {"email": UNKNOWN_EMAIL, "password": WRONG_PHRASE}
    else:
        body = {"email": world.users[caller].email, "password": PHRASE}
    return _client(world.clients, caller).post("/api/v1/auth/login", body, content_type=JSON)


def _logout(world: World, caller: Caller) -> HttpResponseBase:
    return _client(world.logout_clients, caller).post("/api/v1/auth/logout", {}, content_type=JSON)


def _link(world: World, caller: Caller) -> HttpResponseBase:
    email = UNKNOWN_EMAIL if caller is Caller.VISITOR else world.users[caller].email
    return _client(world.clients, caller).post(
        "/api/v1/auth/link", {"email": email}, content_type=JSON
    )


def _verify_token(world: World, caller: Caller) -> str:
    if caller is Caller.VISITOR:
        return _new_link(world.passwordless_patient)
    if caller is Caller.PATIENT:
        return _new_link(world.users[caller])
    return secrets.token_urlsafe(TOKEN_BYTES)  # no link holds this token


def _link_verify(world: World, caller: Caller) -> HttpResponseBase:
    body = {"token": _verify_token(world, caller)}
    return _client(world.clients, caller).post("/api/v1/auth/link/verify", body, content_type=JSON)


def _slots(world: World, caller: Caller) -> HttpResponseBase:
    query = {"appointment_type_id": str(world.appointment_type.pk), **SLOT_WINDOW}
    return _client(world.clients, caller).get("/api/v1/slots", query)


def _book(world: World, caller: Caller) -> HttpResponseBase:
    body: dict[str, object] = {
        "appointment_type_id": str(world.appointment_type.pk),
        "starts_at": BOOKING_STARTS[caller].isoformat(),
    }
    if caller is Caller.CLINICIAN:
        body["patient_id"] = str(world.passwordless_patient.pk)
    if caller is Caller.ADMIN:
        body["clinician_id"] = str(world.clinician.pk)
        body["patient_id"] = str(world.users[Caller.PATIENT].pk)
    return _client(world.clients, caller).post("/api/v1/appointments", body, content_type=JSON)


def _join_waitlist(world: World, caller: Caller) -> HttpResponseBase:
    body: dict[str, object] = {
        "appointment_type_id": str(world.appointment_type.pk),
        "earliest_at": WAITLIST_EARLIEST,
        "latest_at": WAITLIST_LATEST,
    }
    if caller is Caller.ADMIN:
        body["patient_id"] = str(world.passwordless_patient.pk)
    return _client(world.clients, caller).post("/api/v1/waitlist", body, content_type=JSON)


def _reminders(world: World, caller: Caller) -> HttpResponseBase:
    return _client(world.clients, caller).post("/api/v1/jobs/reminders", {}, content_type=JSON)


# Keyed by method and route, as the access rows are. The catch-all row has method ANY; its
# request is a GET to a route no view declares.
SENDERS: dict[tuple[str, str], Sender] = {
    ("GET", "api/v1/health"): _get("/api/v1/health"),
    ("POST", "api/v1/auth/login"): _login,
    ("POST", "api/v1/auth/logout"): _logout,
    ("POST", "api/v1/auth/link"): _link,
    ("POST", "api/v1/auth/link/verify"): _link_verify,
    ("GET", "api/v1/slots"): _slots,
    ("GET", "api/v1/search/providers"): _get("/api/v1/search/providers"),
    ("GET", "api/v1/search/hospitals"): _get("/api/v1/search/hospitals"),
    ("GET", "api/v1/search/specialties"): _get("/api/v1/search/specialties"),
    ("GET", "api/v1/appointments"): _get("/api/v1/appointments"),
    ("POST", "api/v1/appointments"): _book,
    ("POST", "api/v1/waitlist"): _join_waitlist,
    ("POST", "api/v1/jobs/reminders"): _reminders,
    (ANY_METHOD, "^api/v1/"): _get("/api/v1/no-such-route"),
}
