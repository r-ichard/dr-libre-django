"""Task 19, sections 3.1, 4, 10, 12: the user rules that need no stored data."""

import pytest

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.domain.vocabulary import Role

PASSWORD_MESSAGE = FieldMessage("password", "Use 10 to 72 characters.")


def _check_password(raw: str) -> object:
    from scheduling.domain.user_rules import check_password

    return check_password(raw)


@pytest.mark.parametrize("length", [10, 11, 72])
def returns_the_password_when_length_is_allowed(length: int) -> None:
    assert _check_password("p" * length) == Success("p" * length)


@pytest.mark.parametrize("length", [0, 9, 73])
def returns_message_on_password_field_when_length_is_not_allowed(length: int) -> None:
    assert _check_password("p" * length) == Failure.invalid_input([PASSWORD_MESSAGE])


def returns_the_password_untouched_when_it_has_spaces_around_it() -> None:
    assert _check_password("  spaced out  ") == Success("  spaced out  ")


def returns_lower_case_trimmed_email_when_typed_with_capitals_and_spaces() -> None:
    from scheduling.domain.user_rules import check_email

    assert check_email("  Ana.Lopez@Example.TEST ") == Success("ana.lopez@example.test")


@pytest.mark.parametrize(
    "raw", ["", "   ", "no-at-sign", "@example.test", "ana@", "a b@example.test"]
)
def returns_message_on_email_field_when_address_is_not_an_address(raw: str) -> None:
    from scheduling.domain.user_rules import check_email

    assert check_email(raw) == Failure.invalid_input(
        [FieldMessage("email", "Enter an email address like name@example.org.")]
    )


def returns_message_on_email_field_when_address_is_longer_than_254_characters() -> None:
    from scheduling.domain.user_rules import check_email

    assert isinstance(check_email("a" * 245 + "@example.test"), Failure)
    assert check_email("a" * 241 + "@example.test") == Success("a" * 241 + "@example.test")


def returns_message_on_full_name_field_when_name_is_blank() -> None:
    from scheduling.domain.user_rules import check_full_name

    assert check_full_name("   ") == Failure.invalid_input(
        [FieldMessage("full_name", "Enter a name.")]
    )


def returns_trimmed_name_when_name_has_spaces_around_it() -> None:
    from scheduling.domain.user_rules import check_full_name

    assert check_full_name("  Ana Lopez ") == Success("Ana Lopez")


def returns_no_refusal_when_admin_edits_their_own_name() -> None:
    from scheduling.domain.user_rules import own_account_refusals

    assert own_account_refusals(is_own_account=True, deactivates=False, changes_role=False) == []


def returns_no_refusal_when_admin_deactivates_another_account() -> None:
    from scheduling.domain.user_rules import own_account_refusals

    assert own_account_refusals(is_own_account=False, deactivates=True, changes_role=True) == []


def returns_both_reasons_when_admin_deactivates_and_changes_own_role() -> None:
    from scheduling.domain.user_rules import own_account_refusals

    refusals = own_account_refusals(is_own_account=True, deactivates=True, changes_role=True)

    assert refusals == [
        "You cannot deactivate your own account.",
        "You cannot change your own role.",
    ]


def returns_only_the_role_reason_when_admin_changes_own_role() -> None:
    from scheduling.domain.user_rules import own_account_refusals

    refusals = own_account_refusals(is_own_account=True, deactivates=False, changes_role=True)

    assert refusals == ["You cannot change your own role."]


@pytest.mark.parametrize(
    ("active_admins", "target_is_active_admin", "stays_active_admin"),
    [(1, True, False), (0, True, False)],
)
def returns_last_admin_refusal_when_the_only_active_admin_stops_being_one(
    active_admins: int, target_is_active_admin: bool, stays_active_admin: bool
) -> None:
    from scheduling.domain.user_rules import last_admin_refusal

    refusal = last_admin_refusal(active_admins, target_is_active_admin, stays_active_admin)

    assert refusal == "This is the last active admin. Make another admin first."


@pytest.mark.parametrize(
    ("active_admins", "target_is_active_admin", "stays_active_admin"),
    [(2, True, False), (1, True, True), (1, False, False), (1, False, True)],
)
def returns_no_last_admin_refusal_when_another_admin_remains(
    active_admins: int, target_is_active_admin: bool, stays_active_admin: bool
) -> None:
    from scheduling.domain.user_rules import last_admin_refusal

    assert last_admin_refusal(active_admins, target_is_active_admin, stays_active_admin) is None


def _role_refusals(
    current: Role = Role.CLINICIAN,
    new: Role = Role.ADMIN,
    has_profile: bool = False,
    appointments_as_patient: int = 0,
    waitlist_entries: int = 0,
    is_passwordless: bool = False,
) -> list[str]:
    from scheduling.domain.user_rules import RoleFacts, role_change_refusals

    facts = RoleFacts(
        current, new, has_profile, appointments_as_patient, waitlist_entries, is_passwordless
    )
    return role_change_refusals(facts)


def returns_no_refusal_when_clinician_without_profile_becomes_admin() -> None:
    assert _role_refusals() == []


def returns_no_refusal_when_role_stays_the_same_whatever_the_records() -> None:
    refusals = _role_refusals(
        current=Role.CLINICIAN, new=Role.CLINICIAN, has_profile=True, waitlist_entries=2
    )

    assert refusals == []


def returns_profile_reason_when_clinician_with_profile_becomes_patient() -> None:
    refusals = _role_refusals(new=Role.PATIENT, has_profile=True)

    assert refusals == ["This clinician has a profile. Delete the profile first."]


def returns_only_profile_reason_when_clinician_with_profile_and_waitlist_becomes_patient() -> None:
    refusals = _role_refusals(new=Role.PATIENT, has_profile=True, waitlist_entries=2)

    assert refusals == ["This clinician has a profile. Delete the profile first."]


def returns_appointment_and_waitlist_reasons_when_patient_with_both_becomes_admin() -> None:
    refusals = _role_refusals(current=Role.PATIENT, appointments_as_patient=3, waitlist_entries=1)

    assert refusals == [
        "This patient has 3 appointments.",
        "This patient has 1 waitlist entry.",
    ]


def returns_one_appointment_in_singular_when_patient_has_one() -> None:
    refusals = _role_refusals(current=Role.PATIENT, appointments_as_patient=1)

    assert refusals == ["This patient has 1 appointment."]


def returns_no_refusal_when_patient_without_records_becomes_clinician() -> None:
    assert _role_refusals(current=Role.PATIENT, new=Role.CLINICIAN) == []


@pytest.mark.parametrize("new", [Role.ADMIN, Role.CLINICIAN])
def returns_passwordless_reason_when_passwordless_patient_changes_role(new: Role) -> None:
    refusals = _role_refusals(current=Role.PATIENT, new=new, is_passwordless=True)

    assert refusals == ["This patient has no password, so the role cannot change."]


def returns_reason_when_passwordless_patient_changes_email() -> None:
    from scheduling.domain.user_rules import email_change_refusal

    assert email_change_refusal(is_passwordless=True) == (
        "This patient has no password, so the verified email is the only way in."
    )


def returns_no_reason_when_user_with_a_password_changes_email() -> None:
    from scheduling.domain.user_rules import email_change_refusal

    assert email_change_refusal(is_passwordless=False) is None


def returns_waitlist_entries_in_plural_when_patient_has_two() -> None:
    refusals = _role_refusals(current=Role.PATIENT, waitlist_entries=2)

    assert refusals == ["This patient has 2 waitlist entries."]
