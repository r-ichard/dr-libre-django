"""Section 14: POST /auth/login and POST /auth/logout."""

from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.domain.failure import Failure
from scheduling.use_cases.session import sign_out
from scheduling.use_cases.sign_in import sign_in_with_password
from scheduling.views.access import public
from scheduling.views.api_view import ApiView
from scheduling.views.auth_schemas import LoginRequest, LogoutRequest
from scheduling.views.failure_response import failure_response
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
