"""Section 7.3 pages: ask for a link from the sign-in page, "Check your email", and the page
with the Continue button. Opening the link uses nothing; only the button's POST does, so a mail
scanner that opens the link cannot spend it."""

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.sign_in_rules import Home
from scheduling.use_cases.sign_in_link import ask_for_link, use_link
from scheduling.views.network_address import network_address
from scheduling.views.pages.homes import HOME_PATHS
from scheduling.views.pages.page_view import PageView, render_page
from scheduling.views.pages.sign_in import LinkForm, SignInForm, SignInPage
from scheduling.views.session_cookie import set_session_cookie

CHECK_EMAIL_PATH = "/sign-in/check-email"
EMAIL_MISSING = "Enter your email address."
EMAIL_INVALID = "Enter a valid email address."
INVALID_TEMPLATE = "sign_in_link_invalid.html"
TOO_MANY_LINKS = "Too many sign-in links were asked for. Try again in an hour."
PATIENT_HOME = HOME_PATHS[Home.PATIENT_PORTAL]


class LinkRequestPage(SignInPage):
    """POST only: the form lives on the sign-in page."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest) -> HttpResponse:
        email = request.POST.get("link_email", "").strip()
        if not email:
            return self._refused(request, email, EMAIL_MISSING, 400)
        asked = ask_for_link(email, network_address(request))
        if isinstance(asked, Failure):
            rate_limited = asked.code == FailureCode.RATE_LIMITED
            message = TOO_MANY_LINKS if rate_limited else EMAIL_INVALID
            return self._refused(request, email, message, 429 if rate_limited else 400)
        return HttpResponseRedirect(CHECK_EMAIL_PATH, status=303)

    def _refused(self, request: HttpRequest, email: str, message: str, status: int) -> HttpResponse:
        link_form = LinkForm(email=email, error=message)
        return self._form(request, SignInForm(), link_form, status)


class CheckEmailPage(PageView):
    template_name = "check_email.html"


class LinkContinuePage(PageView):
    """The same page for every token: GET reads nothing from the database."""

    template_name = "sign_in_link.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return _origin_only_referrer(self.page(request))

    def post(self, request: HttpRequest) -> HttpResponse:
        # The form has no action, so the browser posts to the address it opened, token included.
        token = request.POST.get("token") or request.GET.get("token", "")
        used = use_link(token, request.headers.get("User-Agent", ""))
        if isinstance(used, Failure):
            invalid = render_page(request, INVALID_TEMPLATE, status=400)
            return _origin_only_referrer(invalid)
        response = HttpResponseRedirect(PATIENT_HOME, status=303)
        set_session_cookie(response, used.value.token, used.value.session.expires_at)
        return _origin_only_referrer(response)


def _origin_only_referrer[Response: HttpResponse](response: Response) -> Response:
    response["Referrer-Policy"] = "strict-origin"
    return response
