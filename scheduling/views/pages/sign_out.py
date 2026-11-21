"""Section 12.2: signing out is a POST; CSRF protection comes from the middleware."""

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views import View

from scheduling.use_cases.session import sign_out
from scheduling.views.pages.page_view import SIGN_IN_PATH
from scheduling.views.session_cookie import SESSION_COOKIE, clear_session_cookie


class SignOutPage(View):
    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        token = request.COOKIES.get(SESSION_COOKIE)
        if token:
            sign_out(token)
        response = HttpResponseRedirect(SIGN_IN_PATH)
        clear_session_cookie(response)
        return response
