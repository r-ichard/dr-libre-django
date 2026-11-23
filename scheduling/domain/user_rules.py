"""User rules that need no stored data, spec 3.1, 4, 10 and 12."""

from dataclasses import dataclass

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.visitor_rules import is_valid_email
from scheduling.domain.vocabulary import Role

PASSWORD_MINIMUM = 10
PASSWORD_MAXIMUM = 72
OWN_DEACTIVATION = "You cannot deactivate your own account."
OWN_ROLE = "You cannot change your own role."
LAST_ADMIN = "This is the last active admin. Make another admin first."
HAS_PROFILE = "This clinician has a profile. Delete the profile first."
PASSWORDLESS_ROLE = "This patient has no password, so the role cannot change."
PASSWORDLESS_EMAIL = "This patient has no password, so the verified email is the only way in."


def check_password(raw: str) -> Result[str]:
    """The password is kept exactly as typed: spaces count, since they will be typed again."""
    if PASSWORD_MINIMUM <= len(raw) <= PASSWORD_MAXIMUM:
        return Success(raw)
    message = f"Use {PASSWORD_MINIMUM} to {PASSWORD_MAXIMUM} characters."
    return Failure.invalid_input([FieldMessage("password", message)])


def check_email(raw: str) -> Result[str]:
    """Stored in lower case so that two spellings of one address are one address."""
    address = raw.strip().lower()
    if is_valid_email(address):
        return Success(address)
    message = "Enter an email address like name@example.org."
    return Failure.invalid_input([FieldMessage("email", message)])


def check_full_name(raw: str) -> Result[str]:
    name = raw.strip()
    if name:
        return Success(name)
    return Failure.invalid_input([FieldMessage("full_name", "Enter a name.")])


def own_account_refusals(
    *, is_own_account: bool, deactivates: bool, changes_role: bool
) -> list[str]:
    if not is_own_account:
        return []
    refusals = [OWN_DEACTIVATION] if deactivates else []
    return [*refusals, OWN_ROLE] if changes_role else refusals


def last_admin_refusal(
    active_admins: int, target_is_active_admin: bool, stays_active_admin: bool
) -> str | None:
    if target_is_active_admin and not stays_active_admin and active_admins <= 1:
        return LAST_ADMIN
    return None


@dataclass(frozen=True)
class RoleFacts:
    current: Role
    new: Role
    has_profile: bool
    appointments_as_patient: int
    waitlist_entries: int
    is_passwordless: bool


def role_change_refusals(facts: RoleFacts) -> list[str]:
    if facts.current == facts.new:
        return []
    if facts.current == Role.CLINICIAN:
        return [HAS_PROFILE] if facts.has_profile else []
    if facts.current != Role.PATIENT:
        return []
    refusals = []
    if facts.appointments_as_patient:
        refusals.append(_count_sentence(facts.appointments_as_patient, "appointment"))
    if facts.waitlist_entries:
        refusals.append(
            _count_sentence(facts.waitlist_entries, "waitlist entry", "waitlist entries")
        )
    if facts.is_passwordless:
        refusals.append(PASSWORDLESS_ROLE)
    return refusals


def email_change_refusal(*, is_passwordless: bool) -> str | None:
    return PASSWORDLESS_EMAIL if is_passwordless else None


def _count_sentence(count: int, singular: str, plural: str = "") -> str:
    noun = singular if count == 1 else plural or f"{singular}s"
    return f"This patient has {count} {noun}."
