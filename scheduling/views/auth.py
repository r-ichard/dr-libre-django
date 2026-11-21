"""Section 14: POST /auth/login, /auth/logout, /auth/link and /auth/link/verify."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.domain.sign_in_rules import home_for
from scheduling.domain.vocabulary import Role
from scheduling.use_cases.session import sign_out
from scheduling.use_cases.sign_in import sign_in_with_password
from scheduling.use_cases.sign_in_link import ask_for_link, use_link
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.auth_schemas import (
    LinkRequest,
    LinkVerifyRequest,
    LoginRequest,
    LogoutRequest,
)
from scheduling.views.failure_response import failure_response
from scheduling.views.network_address import network_address
from scheduling.views.schemas import validate_body
from scheduling.views.session_cookie import SESSION_COOKIE, clear_session_cookie, set_session_cookie


class LoginView(ApiView):
    permission_classes = public()

    def post(self, request: Request) -> Response:
        body = validate_body(LoginRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        user_agent = request.headers.get("User-Agent", "")
        result = sign_in_with_password(
            str(body.value["email"]), str(body.value["password"]), user_agent
        )
        if isinstance(result, Failure):
            return failure_response(result)
        opened = result.value.opened
        response = Response({"home": result.value.home.value})
        set_session_cookie(response, opened.token, opened.session.expires_at)
        return response


class LogoutView(ApiView):
    """Open to anyone: signing out without a session is not an error, it clears the cookie."""

    permission_classes = public()

    def post(self, request: Request) -> Response:
        body = validate_body(LogoutRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        token = request.COOKIES.get(SESSION_COOKIE)
        if token:
            sign_out(token)
        response = Response(status=204)
        clear_session_cookie(response)
        return response


class LinkView(ApiView):
    """The answer never depends on what the address belongs to: 202 and an empty object."""

    permission_classes = public()

    def post(self, request: Request) -> Response:
        body = validate_body(LinkRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        asked = ask_for_link(str(body.value["email"]), network_address(request))
        if isinstance(asked, Failure):
            return failure_response(asked)
        return Response({}, status=202)


class LinkVerifyView(ApiView):
    permission_classes = public()

    def post(self, request: Request) -> Response:
        body = validate_body(LinkVerifyRequest, request.data)
        if isinstance(body, Failure):
            return failure_response(body)
        user_agent = request.headers.get("User-Agent", "")
        used = use_link(str(body.value["token"]), user_agent)
        if isinstance(used, Failure):
            return failure_response(used)
        response = Response({"home": home_for(Role.PATIENT).value})
        set_session_cookie(response, used.value.token, used.value.session.expires_at)
        return response
