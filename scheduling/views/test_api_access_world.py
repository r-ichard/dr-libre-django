"""The accounts and bookable time of the walk over routes that name no record: a clinic with one
clinician, a patient with a password, a patient without one, an admin, and signed-in clients."""

import secrets
from dataclasses import dataclass

from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.domain.sign_in_link_rules import LINK_LIFETIME
from scheduling.models import AppointmentType, ClinicianProfile, Department, User
from scheduling.models.builders import add_clinician, make
from scheduling.use_cases.session import hash_token
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.session_cookie import SESSION_COOKIE
from scheduling.views.test_api_access_rows import Caller

PHRASE = "correct horse battery staple"
LOGIN = "/api/v1/auth/login"
TOKEN_BYTES = 32


@dataclass(frozen=True)
class World:
    appointment_type: AppointmentType
    clinician: ClinicianProfile
    users: dict[Caller, User]  # the account of each signed-in caller
    passwordless_patient: User
    clients: dict[Caller, Client]  # signed in, one per caller
    logout_clients: dict[Caller, Client]  # signed in, used by the logout row only


def _user(role: str) -> User:
    user = make("User", role=role, password=make_password(PHRASE))
    assert isinstance(user, User)
    return user


def _passwordless_patient() -> User:
    user = make(
        "User",
        role="PATIENT",
        password=make_password(None),
        email_verified_at=clock.now_utc(),
    )
    assert isinstance(user, User)
    return user


def _sign_in(user: User) -> Client:
    client = browser_api_client()
    response = client.post(
        LOGIN, {"email": user.email, "password": PHRASE}, content_type="application/json"
    )
    assert response.status_code == 200
    return client


def _build_world() -> World:
    department = make("Department")
    assert isinstance(department, Department)
    appointment_type = make("AppointmentType", department=department)
    assert isinstance(appointment_type, AppointmentType)
    users = {
        Caller.PATIENT: _user("PATIENT"),
        Caller.CLINICIAN: _user("CLINICIAN"),
        Caller.ADMIN: _user("ADMIN"),
    }
    clinician = add_clinician(department, user=users[Caller.CLINICIAN])
    clients = {caller: _sign_in(user) for caller, user in users.items()}
    logout_clients = {caller: _sign_in(user) for caller, user in users.items()}
    # The walk's own login row would sign a client in later, which would hide a client that
    # arrives unsigned, so the cookie is checked here.
    assert all(
        SESSION_COOKIE in client.cookies for client in [*clients.values(), *logout_clients.values()]
    )
    return World(
        appointment_type=appointment_type,
        clinician=clinician,
        users=users,
        passwordless_patient=_passwordless_patient(),
        clients=clients,
        logout_clients=logout_clients,
    )


def _new_link(patient: User) -> str:
    """Made at send time: asking for a link cancels the open links of the same address."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    make(
        "SignInLink",
        patient=patient,
        token_hash=hash_token(token),
        expires_at=clock.now_utc() + LINK_LIFETIME,
    )
    return token
