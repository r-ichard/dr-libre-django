"""Task 15: the patient's profile (phone, date of birth) and change password. The patient is the
session's user; a passwordless patient gets 404 for the password page."""

from django.http import Http404, HttpRequest, HttpResponse

from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.profile import ProfileCommand, change_password, update_profile
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.portal_forms import (
    day_or_none,
    failure_messages,
    forget_notice,
    redirect_with_notice,
    summary_items,
    take_notice,
)

PROFILE_PATH = "/patient/profile"
PASSWORD_PATH = "/patient/profile/password"  # noqa: S105 - a page path, not a secret
NOTICES = {
    "saved": "Your profile is saved.",
    "password-changed": "Your password is changed. Other devices are signed out.",
}
REAL_DATE = "Enter a real date, for example 1990-03-27."


class ProfilePage(PageView):
    template_name = "patient/profile.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        born = self.user.date_of_birth
        entered = {"phone": self.user.phone, "date_of_birth": born.isoformat() if born else ""}
        return self._render(request, entered, {})

    def post(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        entered = {name: request.POST.get(name, "").strip() for name in ("phone", "date_of_birth")}
        born = day_or_none(entered["date_of_birth"])
        if entered["date_of_birth"] and born is None:
            return self._render(request, entered, {"date_of_birth": REAL_DATE}, 422)
        saved = update_profile(ProfileCommand(entered["phone"], born), self.user)
        if isinstance(saved, Failure):
            return self._render(request, entered, failure_messages(saved), 422)
        return redirect_with_notice(PROFILE_PATH, "saved")

    def _render(
        self,
        request: HttpRequest,
        entered: dict[str, str],
        errors: dict[str, str],
        status: int = 200,
    ) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        context = {
            "notice": take_notice(request, NOTICES),
            "entered": entered,
            "errors": errors,
            "summary": summary_items(errors),
            "has_password": self.user.has_usable_password(),
            "password_path": PASSWORD_PATH,
            "today": current_request_context().now.date().isoformat(),
        }
        return forget_notice(request, self.page(request, context, status))


class PasswordPage(PageView):
    template_name = "patient/password.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        self._require_password()
        return self._render(request, {})

    def post(self, request: HttpRequest) -> HttpResponse:
        user = self._require_password()
        current = request.POST.get("current_password", "")
        new = request.POST.get("new_password", "")
        keep = self.resolved.session.pk if self.resolved else None
        changed = change_password(current, new, user, keep)
        if isinstance(changed, Failure):
            return self._render(request, failure_messages(changed), 422)
        return redirect_with_notice(PROFILE_PATH, "password-changed")

    def _require_password(self) -> User:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        if not self.user.has_usable_password():
            raise Http404
        return self.user

    def _render(
        self, request: HttpRequest, errors: dict[str, str], status: int = 200
    ) -> HttpResponse:
        context = {"errors": errors, "summary": summary_items(errors), "profile_path": PROFILE_PATH}
        return self.page(request, context, status)
