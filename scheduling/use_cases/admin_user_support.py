"""Section 10: what the user writes share: the lock order, the clean values and the side effects
of a deactivation or a changed address. The admin comes from the session, never from the payload."""

from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Q

from scheduling.domain import record_fields, user_rules
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import Role
from scheduling.models import Session, SignInLink, User
from scheduling.use_cases.request_context import current_request_context

EMAIL_TAKEN = "Email is taken."
CHOOSE_ROLE = "Choose a role."
USE_DEACTIVATE_STEP = "Use the Deactivate step to deactivate an account."
NUL_MESSAGE = record_fields.NULL_MESSAGE
FORM_FIELDS = ("full_name", "email", "role", "password", "is_active")


@dataclass(frozen=True)
class Locked:
    """The admin, the user acted on and how many active admins there are, all read under lock."""

    admin: User | None
    target: User | None
    active_admins: int


def lock_users(actor_id: UUID, target_id: UUID | None) -> Locked:
    """One lock order for everybody (primary key): admins acting on each other wait in turn."""
    wanted = Q(pk=actor_id) | Q(role=Role.ADMIN, is_active=True)
    if target_id is not None:
        wanted |= Q(pk=target_id)
    rows = list(User.objects.select_for_update().filter(wanted).order_by("pk"))
    by_id = {row.pk: row for row in rows}
    admin = by_id.get(actor_id)
    is_admin = admin is not None and admin.is_active and Role(admin.role) == Role.ADMIN
    active = sum(1 for row in rows if row.is_active and Role(row.role) == Role.ADMIN)
    target = by_id.get(target_id) if target_id is not None else None
    return Locked(admin if is_admin else None, target, active)


def cleaned_values(
    values: dict[str, object], *, creating: bool
) -> tuple[dict[str, object], list[FieldMessage]]:
    """Only the user's own form fields get through, each checked by the domain."""
    wanted = {key: values[key] for key in FORM_FIELDS if key in values}
    if creating:
        for key in ("full_name", "email", "password"):
            wanted.setdefault(key, "")
    cleaned: dict[str, object] = {}
    messages: list[FieldMessage] = []
    for key, value in wanted.items():
        checked = _clean_field(key, value)
        if isinstance(checked, Failure):
            fields = checked.details["fields"]
            if isinstance(fields, list):
                messages += [
                    FieldMessage(str(i["field"]), str(i["message"]))
                    for i in fields
                    if isinstance(i, dict)
                ]
        else:
            cleaned[key] = checked.value
    return cleaned, messages


def _clean_field(key: str, value: object) -> Result[object]:
    text = value if isinstance(value, str) else ""
    if "\x00" in text:
        return Failure.invalid_input([FieldMessage(key, NUL_MESSAGE)])
    match key:
        case "full_name":
            return record_fields.check_text("full_name", text, 200, "Enter a name.")
        case "email":
            return user_rules.check_email(text)
        case "password":
            return user_rules.check_password(text)
        case "role":
            return _role_of(text)
        case _:
            return _flag(value)


def _role_of(text: str) -> Result[object]:
    try:
        return Success(Role(text).value)
    except ValueError:
        return Failure.invalid_input([FieldMessage("role", CHOOSE_ROLE)])


def _flag(value: object) -> Result[object]:
    return Success(value is True)


def email_is_taken(email: str, own_id: UUID | None) -> bool:
    taken = User.objects.filter(email__iexact=email)
    return (taken.exclude(pk=own_id) if own_id else taken).exists()


def is_email_conflict(error: IntegrityError) -> bool:
    diag = getattr(error.__cause__, "diag", None)
    return getattr(diag, "constraint_name", "") == "user_email_unique"


def end_access(user: User) -> tuple[int, int]:
    """Cancel the unused sign-in links first, then end the sessions: a link used at this very
    moment either finished before (its session goes now) or waits on the lock and finds it
    cancelled. Returns how many sessions and links ended."""
    now = current_request_context().now
    links = SignInLink.objects.filter(
        patient=user, used_at__isnull=True, cancelled_at__isnull=True
    ).update(cancelled_at=now)
    sessions, _ = Session.objects.filter(user=user).delete()
    return sessions, links
