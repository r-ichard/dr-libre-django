"""Turns the session cookie into the request's user. A missing, unknown, expired or deactivated
session is anonymous, not an error, so a public endpoint stays public."""

from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request

from scheduling.domain.failure import Failure
from scheduling.models import User
from scheduling.use_cases.session import ResolvedSession, resolve_session
from scheduling.views.session_cookie import SESSION_COOKIE


class SessionCookieAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[User, ResolvedSession] | None:
        token = request.COOKIES.get(SESSION_COOKIE)
        if not token:
            return None
        result = resolve_session(token)
        if isinstance(result, Failure):
            return None
        return result.value.user, result.value
