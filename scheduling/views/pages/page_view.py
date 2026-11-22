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
from scheduling.domain.rate_limit_rules import RateLimitScope, wait_sentence
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.read_limits import take_read_hit
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import ResolvedSession, resolve_session
from scheduling.views.network_address import network_address
from scheduling.views.pages.admin_notices import forget_admin_notice, take_admin_notice
from scheduling.views.session_cookie import SESSION_COOKIE, set_session_cookie

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
    resolved: ResolvedSession | None = None
    read_scope: RateLimitScope | None = None

    def dispatch(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponseBase:
        response = self._guarded_dispatch(request, *args, **kwargs)
        # The server moved expires_at; without a fresh cookie the browser drops the old one.
        resolved = self.resolved
        if resolved and resolved.extended and SESSION_COOKIE not in response.cookies:
            set_session_cookie(
                response, request.COOKIES[SESSION_COOKIE], resolved.session.expires_at
            )
        return response

    def _guarded_dispatch(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponseBase:
        self.resolved = self._resolve_session(request)
        self.user = self.resolved.user if self.resolved else None
        if self.allowed_roles is not None:
            if self.user is None:
                query = urlencode({"next": request.get_full_path()}, safe="/")
                return HttpResponseRedirect(f"{SIGN_IN_PATH}?{query}")
            if Role(self.user.role) not in self.allowed_roles:
                return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)
        if request.method == "GET" and self.read_scope is not None:
            wait = take_read_hit(self.read_scope, self.user, network_address(request))
            if wait is not None:
                return self._limited_page(request, wait)
        if request.method == "GET" and type(self).get is PageView.get and not self.template_name:
            return self.http_method_not_allowed(request)
        return super().dispatch(request, *args, **kwargs)

    def _limited_page(self, request: HttpRequest, wait: int) -> HttpResponse:
        """Keeps the layout and a way on: the same address, to try again."""
        context = {
            "heading": "Too many requests",
            "message": f"You looked at too many pages. {wait_sentence(wait)}",
            "action_href": request.get_full_path(),
            "action_text": "Try again",
        }
        response = render_page(
            request, "booking/refused.html", context, status=429, signed_in_user=self.user
        )
        response["Retry-After"] = str(wait)
        return response

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(request)

    def page(
        self, request: HttpRequest, context: Mapping[str, object] | None = None, status: int = 200
    ) -> HttpResponse:
        shows_notice = self.shows_admin_notice(request, status)
        notice = take_admin_notice(request) if shows_notice else ""
        response = render_page(
            request,
            self.template_name,
            {**(context or {}), "admin_notice": notice},
            status=status,
            signed_in_user=self.user,
        )
        return forget_admin_notice(request, response) if shows_notice else response

    def shows_admin_notice(self, request: HttpRequest, status: int) -> bool:
        """Only an admin's page that answers a GET takes the notice, so it is shown once."""
        admin_only = self.allowed_roles == frozenset({Role.ADMIN})
        return admin_only and request.method == "GET" and status == 200

    @staticmethod
    def _resolve_session(request: HttpRequest) -> ResolvedSession | None:
        token = request.COOKIES.get(SESSION_COOKIE)
        if not token:
            return None
        result = resolve_session(token)
        return None if isinstance(result, Failure) else result.value
