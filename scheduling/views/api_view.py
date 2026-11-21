from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduling.use_cases.session import ResolvedSession
from scheduling.views.access import public
from scheduling.views.authentication import SessionCookieAuthentication
from scheduling.views.session_cookie import SESSION_COOKIE, set_session_cookie

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class ApiView(APIView):
    """Base for API views: head and options are not routes, and no Allow header is sent.
    Cookie-authenticated writes are CSRF-safe by two layers: the SameSite=Strict cookie and the
    Origin check in initial()."""

    http_method_names = ["get", "post", "put", "patch", "delete"]
    authentication_classes = [SessionCookieAuthentication]

    @property
    def default_response_headers(self) -> dict[str, str]:
        headers = super().default_response_headers
        headers.pop("Allow", None)
        return headers

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        refuse_foreign_origin(request)
        super().initial(request, *args, **kwargs)

    def finalize_response(
        self, request: Request, response: Response, *args: object, **kwargs: object
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        # Errors skip this so a refused request never triggers authentication of its own.
        if response.status_code < 400 and SESSION_COOKIE not in response.cookies:
            resolved = request.auth
            if isinstance(resolved, ResolvedSession) and resolved.extended:
                set_session_cookie(
                    response, request.COOKIES[SESSION_COOKIE], resolved.session.expires_at
                )
        return response


def refuse_foreign_origin(request: Request) -> None:
    """A browser sends Origin on every cross-origin write; a client that sends none is not a
    browser and cannot ride a victim's cookie. "null" matches nothing, so it is refused."""
    origin = request.headers.get("Origin")
    if request.method in SAFE_METHODS or origin is None:
        return
    own_origin = f"{request.scheme}://{request.get_host()}"
    if origin != own_origin and origin not in settings.CSRF_TRUSTED_ORIGINS:
        raise PermissionDenied


class NotFoundView(ApiView):
    """Catch-all under the API prefix, so unknown paths answer in the contract's shape."""

    permission_classes = public()
