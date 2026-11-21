"""Section 12.1: the sign-in screen, a plain form that works without JavaScript."""

from dataclasses import dataclass, field

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.failure import Failure
from scheduling.domain.sign_in_rules import home_for
from scheduling.models.people import Role
from scheduling.use_cases.sign_in import is_locked_out, sign_in_with_password
from scheduling.views.pages.homes import HOME_PATHS
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.safe_redirect import local_path_or_home
from scheduling.views.session_cookie import set_session_cookie

WRONG_CREDENTIALS = "Email or password is not correct."
LOCKED_OUT = "Too many attempts. Try again in 15 minutes."
MISSING_MESSAGES = {"email": "Enter your email address.", "password": "Enter your password."}
FORM_ERROR_ID = "form-error"


@dataclass(frozen=True)
class SummaryItem:
    target: str
    message: str
    id: str = ""


@dataclass
class SignInForm:
    email: str = ""
    next_path: str = ""
    field_errors: dict[str, str] = field(default_factory=dict)
    form_error: str = ""
    focus: str = ""

    @property
    def focus_email(self) -> bool:
        return self.focus == "email"

    @property
    def focus_password(self) -> bool:
        return self.focus == "password"

    @property
    def summary(self) -> list[SummaryItem]:
        if self.form_error:
            return [SummaryItem("id_email", self.form_error, FORM_ERROR_ID)]
        return [SummaryItem(f"id_{name}", text) for name, text in self.field_errors.items()]


class SignInPage(PageView):
    template_name = "sign_in.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if self.user is not None:
            return HttpResponseRedirect(HOME_PATHS[home_for(Role(self.user.role))])
        return self._form(
            request, SignInForm(next_path=local_path_or_home(request.GET.get("next", ""), ""))
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        next_path = local_path_or_home(request.POST.get("next", ""), "")
        form = SignInForm(email=email, next_path=next_path)
        entered = {"email": email, "password": password}
        form.field_errors = {
            name: MISSING_MESSAGES[name] for name, value in entered.items() if not value
        }
        if form.field_errors:
            form.focus = next(iter(form.field_errors))
            return self._form(request, form)
        result = sign_in_with_password(email, password, request.headers.get("User-Agent", ""))
        if isinstance(result, Failure):
            form.form_error = LOCKED_OUT if is_locked_out(email) else WRONG_CREDENTIALS
            form.focus = "email"
            return self._form(request, form)
        opened = result.value.opened
        target = local_path_or_home(next_path, HOME_PATHS[result.value.home])
        response = HttpResponseRedirect(target)
        set_session_cookie(response, opened.token, opened.session.expires_at)
        return response

    def _form(self, request: HttpRequest, form: SignInForm) -> HttpResponse:
        return self.page(request, {"form": form, "form_error_id": FORM_ERROR_ID})
