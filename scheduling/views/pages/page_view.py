"""Base for server-rendered pages: resolves the session cookie, guards by role, renders in the
layout. Authorization comes from the session's user, never from the request."""

from collections.abc import Mapping
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from django.views import View

from scheduling.domain.failure import Failure
from scheduling.models import User
from scheduling.models.people import Role
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import resolve_session
from scheduling.views.session_cookie import SESSION_COOKIE

SIGN_IN_PATH = "/sign-in"


def correlation_id_or_blank() -> str:
    try:
        return current_request_context().correlation_id
    except LookupError:
        return ""


def render_page(
    request: HttpRequest,
    template_name: str,
    context: Mapping[str, object] | None = None,
    *,
    status: int = 200,
    signed_in_user: User | None = None,
) -> HttpResponse:
    full_context = {
        **(context or {}),
        "signed_in_user": signed_in_user,
        "correlation_id": correlation_id_or_blank(),
    }
    response = render(request, template_name, full_context, status=status)
    add_never_cache_headers(response)
    return response


class PageView(View):
    template_name = ""
    allowed_roles: frozenset[Role] | None = None
    user: User | None = None

    def dispatch(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseBase:
        self.user = self._resolve_user(request)
        if self.allowed_roles is not None:
            if self.user is None:
                query = urlencode({"next": request.get_full_path()}, safe="/")
                return HttpResponseRedirect(f"{SIGN_IN_PATH}?{query}")
            if Role(self.user.role) not in self.allowed_roles:
                return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(request)

    def page(
        self, request: HttpRequest, context: Mapping[str, object] | None = None, status: int = 200
    ) -> HttpResponse:
        return render_page(
            request, self.template_name, context, status=status, signed_in_user=self.user
        )

    @staticmethod
    def _resolve_user(request: HttpRequest) -> User | None:
        token = request.COOKIES.get(SESSION_COOKIE)
        if not token:
            return None
        result = resolve_session(token)
        return None if isinstance(result, Failure) else result.value.user
