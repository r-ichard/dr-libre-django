"""The patient's profile (phone, date of birth) and change password. The patient is the
session's user; a passwordless patient gets 404 for the password page."""

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect

from scheduling.domain.date_parts import BIRTH_PARTS, read_birth_date
from scheduling.domain.failure import Failure
from scheduling.domain.vocabulary import Role
from scheduling.models import User
from scheduling.use_cases.profile import ProfileCommand, change_password, update_profile
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.page_view import PageView
from scheduling.views.pages.portal_forms import (
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


def _summary(errors: dict[str, str]) -> list[dict[str, str]]:
    """The group's error points at its first input; no element has the bare field's id."""
    items = summary_items(errors)
    for item in items:
        if item["target"] == "id_date_of_birth":
            item["target"] = "id_date_of_birth_day"
    return items


class ProfilePage(PageView):
    template_name = "patient/profile.html"
    allowed_roles = frozenset({Role.PATIENT})

    def get(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        born = self.user.date_of_birth
        parts = (str(born.day), str(born.month), str(born.year)) if born else ("", "", "")
        entered = {"phone": self.user.phone, **dict(zip(BIRTH_PARTS, parts, strict=True))}
        return self._render(request, entered, {})

    def post(self, request: HttpRequest) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        entered = {name: request.POST.get(name, "").strip() for name in ("phone", *BIRTH_PARTS)}
        today = current_request_context().now.date()
        day, month, year = (entered[part] for part in BIRTH_PARTS)
        born = read_birth_date(day, month, year, today, required=False)
        if isinstance(born, Failure):
            return self._render(request, entered, failure_messages(born), 422)
        saved = update_profile(ProfileCommand(entered["phone"], born.value), self.user)
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
            "summary": _summary(errors),
            "has_password": self.user.has_usable_password(),
            "password_path": PASSWORD_PATH,
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
        return self._done()

    def _done(self) -> HttpResponse:
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


class AccountPasswordPage(PasswordPage):
    """Task 19: a clinician or an admin replaces the temporary password an admin set. Same use
    case as the patient's page; it checks the current password and ends the other sessions."""

    template_name = "account/password.html"
    allowed_roles = frozenset({Role.CLINICIAN, Role.ADMIN})

    def _done(self) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        home = "/admin-console/" if Role(self.user.role) == Role.ADMIN else "/clinician/today"
        return HttpResponseRedirect(home, status=303)
