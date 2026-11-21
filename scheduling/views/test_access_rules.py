"""Section 12.3: access declarations a view states, identity from the session, cookie reissue."""

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.urls import path
from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.request_context import RequestContext
from scheduling.models import Session, User
from scheduling.models.access import SessionKind
from scheduling.models.builders import make
from scheduling.models.people import Role
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.session import open_session
from scheduling.views import clock
from scheduling.views.access import public, roles, signed_in, signed_in_user
from scheduling.views.api_view import ApiView

pytestmark = pytest.mark.django_db

COOKIE = "drlibre_session"
RIGHT_PHRASE = "correct horse battery staple"
START = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class PublicView(ApiView):
    permission_classes = public()

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class SignedInView(ApiView):
    permission_classes = signed_in()

    def get(self, request: Request) -> Response:
        return Response({"email": signed_in_user(request).email})


class AdminView(ApiView):
    permission_classes = roles(Role.ADMIN)

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class UndeclaredView(ApiView):
    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class WhoAmIView(ApiView):
    permission_classes = signed_in()

    def post(self, request: Request) -> Response:
        return Response({"email": signed_in_user(request).email})


urlpatterns = [
    path("api/v1/t/public", PublicView.as_view()),
    path("api/v1/t/signed-in", SignedInView.as_view()),
    path("api/v1/t/admin", AdminView.as_view()),
    path("api/v1/t/undeclared", UndeclaredView.as_view()),
    path("api/v1/t/whoami", WhoAmIView.as_view()),
]


@pytest.fixture(autouse=True)
def frozen_clock(settings: object, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.ROOT_URLCONF = "scheduling.views.test_access_rules"  # type: ignore[attr-defined]
    monkeypatch.setattr(clock, "now_utc", lambda: START)


def _signed_in_client(role: str, email: str = "ada@example.test") -> Client:
    user = make("User", email=email, role=role, password=make_password(RIGHT_PHRASE))
    assert isinstance(user, User)
    client = Client()
    with bind_request_context(RequestContext(correlation_id="c", now=START)):
        token = open_session(user, SessionKind.PASSWORD, "").token
    client.cookies[COOKIE] = token
    return client


def returns_401_when_signed_out_user_calls_signed_in_view() -> None:
    response = Client().get("/api/v1/t/signed-in")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def returns_200_with_session_user_when_signed_in_user_calls_signed_in_view() -> None:
    response = _signed_in_client("PATIENT").get("/api/v1/t/signed-in")

    assert response.status_code == 200
    assert response.json() == {"email": "ada@example.test"}


def returns_403_when_patient_calls_admin_view() -> None:
    response = _signed_in_client("PATIENT").get("/api/v1/t/admin")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def returns_401_when_signed_out_user_calls_admin_view() -> None:
    assert Client().get("/api/v1/t/admin").status_code == 401


def returns_200_when_admin_calls_admin_view() -> None:
    assert _signed_in_client("ADMIN").get("/api/v1/t/admin").status_code == 200


def returns_200_when_public_view_is_called_with_stale_cookie() -> None:
    client = Client()
    client.cookies[COOKIE] = "stale-token"

    assert client.get("/api/v1/t/public").status_code == 200


def returns_401_when_signed_in_view_is_called_with_stale_cookie() -> None:
    client = Client()
    client.cookies[COOKIE] = "stale-token"

    assert client.get("/api/v1/t/signed-in").status_code == 401


def returns_closed_when_view_declares_no_access() -> None:
    assert Client().get("/api/v1/t/undeclared").status_code == 401
    assert _signed_in_client("ADMIN").get("/api/v1/t/undeclared").status_code == 403


def returns_user_from_cookie_when_body_names_another_user_id() -> None:
    other = make("User", email="other@example.test")
    client = _signed_in_client("PATIENT")

    response = client.post(
        "/api/v1/t/whoami", {"user_id": str(other.pk)}, content_type="application/json"
    )

    assert response.json() == {"email": "ada@example.test"}


def returns_401_when_user_is_deactivated_after_sign_in() -> None:
    client = _signed_in_client("PATIENT")
    assert client.get("/api/v1/t/signed-in").status_code == 200
    User.objects.update(is_active=False, version=2)

    assert client.get("/api/v1/t/signed-in").status_code == 401


def returns_new_cookie_expiry_when_request_extends_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _signed_in_client("PATIENT")
    later = START + timedelta(days=4)
    monkeypatch.setattr(clock, "now_utc", lambda: later)

    response = client.get("/api/v1/t/signed-in")

    assert Session.objects.get().expires_at == later + timedelta(days=7)
    cookie_expiry = parsedate_to_datetime(response.cookies[COOKIE]["expires"].replace("-", " "))
    assert cookie_expiry == later + timedelta(days=7)


def returns_no_cookie_when_request_does_not_extend_the_session() -> None:
    response = _signed_in_client("PATIENT").get("/api/v1/t/signed-in")

    assert COOKIE not in response.cookies
