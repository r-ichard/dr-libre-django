"""Section 7.1 steps 5 and 6, 7.2, 7.7: the right code books, in one transaction, for the patient
the email identifies."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import date, timedelta

import pytest
from django.core import mail

from scheduling.domain.failure import Failure, Success
from scheduling.models import (
    Appointment,
    AuditLogEntry,
    BookingHold,
    ClinicianProfile,
    Notification,
    Session,
    User,
)
from scheduling.models.access import VerificationCode
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.use_cases.test_booking_support import (
    NOW,
    SLOT,
    THIRTY_MINUTES,
    VISITOR_BIRTH_DATE,
    VISITOR_EMAIL,
    VISITOR_NAME,
    VISITOR_PHONE,
    _at,
    _held,
    _last_code,
    _user_count,
    _verify,
)

pytestmark = pytest.mark.django_db

OnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def _booked_by_visitor(clinic: object, **overrides: object) -> Appointment:
    hold = _held(clinic, **overrides)  # type: ignore[arg-type]
    result = _verify(hold.pk, _last_code())
    assert isinstance(result, Success), result
    appointment = Appointment.objects.get(clinician=hold.clinician)
    return appointment


def returns_patient_with_typed_details_and_no_password_when_email_is_new() -> None:
    clinic = make_clinic()

    appointment = _booked_by_visitor(clinic, reason="Sore knee")

    patient = User.objects.get(email=VISITOR_EMAIL)
    assert appointment.patient_id == patient.pk
    assert patient.role == "PATIENT"
    assert patient.full_name == VISITOR_NAME
    assert patient.date_of_birth == VISITOR_BIRTH_DATE
    assert patient.phone == VISITOR_PHONE
    assert patient.has_usable_password() is False
    assert patient.email_verified_at == NOW
    assert patient.terms_accepted_at == NOW
    assert appointment.patient_reason == "Sore knee"


def returns_online_booking_for_named_clinician_and_hold_and_code_removed() -> None:
    clinic = make_clinic()

    appointment = _booked_by_visitor(clinic)

    assert (appointment.source, appointment.status) == ("ONLINE", "BOOKED")
    assert (appointment.starts_at, appointment.ends_at) == (SLOT, SLOT + THIRTY_MINUTES)
    assert BookingHold.objects.count() == 0
    assert VerificationCode.objects.count() == 0


def returns_round_robin_booking_and_assignment_time_when_none_was_named() -> None:
    clinic = make_clinic()

    appointment = _booked_by_visitor(clinic, clinician_id=None)

    assert appointment.source == "ROUND_ROBIN"
    assert appointment.clinician_id == clinic.clinician.pk
    assigned = ClinicianProfile.objects.get(pk=clinic.clinician.pk).last_assigned_at
    assert assigned == NOW


def returns_booking_code_session_for_24_hours_when_code_is_right() -> None:
    hold = _held(make_clinic())

    result = _verify(hold.pk, _last_code())

    assert isinstance(result, Success)
    session = Session.objects.get()
    assert session.user.email == VISITOR_EMAIL
    assert session.opened_by == "BOOKING_CODE"
    assert session.expires_at == NOW + timedelta(hours=24)
    assert result.value.token  # type: ignore[attr-defined]


def returns_existing_patient_booking_with_profile_unchanged_when_email_has_account() -> None:
    clinic = make_clinic()
    existing = make(
        "User",
        email=VISITOR_EMAIL,
        full_name="Real Name",
        phone="+1 555",
        date_of_birth=date(1970, 5, 5),
    )

    users_before = _user_count()

    appointment = _booked_by_visitor(clinic)

    existing.refresh_from_db()
    assert appointment.patient_id == existing.pk
    assert (existing.full_name, existing.phone) == ("Real Name", "+1 555")  # type: ignore[attr-defined]
    assert existing.date_of_birth == date(1970, 5, 5)  # type: ignore[attr-defined]
    assert _user_count() == users_before


@pytest.mark.parametrize("role", ["ADMIN", "CLINICIAN"])
def returns_forbidden_and_books_nothing_when_email_belongs_to_staff(role: str) -> None:
    clinic = make_clinic()
    make("User", email=VISITOR_EMAIL, role=role)
    hold = _held(clinic)
    users_before = _user_count()

    result = _verify(hold.pk, _last_code())

    assert result == Failure.forbidden()
    assert Appointment.objects.count() == 0
    assert _user_count() == users_before
    assert BookingHold.objects.filter(pk=hold.pk).exists()
    assert Session.objects.count() == 0


def returns_forbidden_when_email_belongs_to_inactive_patient() -> None:
    clinic = make_clinic()
    make("User", email=VISITOR_EMAIL, is_active=False)
    hold = _held(clinic)

    result = _verify(hold.pk, _last_code())

    assert result == Failure.forbidden()
    assert Appointment.objects.count() == 0
    assert BookingHold.objects.filter(pk=hold.pk).exists()


def returns_conflict_and_no_account_when_slot_was_taken_after_the_hold() -> None:
    clinic = make_clinic()
    hold = _held(clinic)
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        starts_at=SLOT,
        ends_at=SLOT + THIRTY_MINUTES,
    )
    users_before = _user_count()

    result = _verify(hold.pk, _last_code())

    assert result == Failure.conflict(["clinician"])
    assert _user_count() == users_before
    assert Appointment.objects.count() == 1
    assert BookingHold.objects.filter(pk=hold.pk).exists()
    assert VerificationCode.objects.filter(hold=hold).exists()
    assert Session.objects.count() == 0


def returns_hold_for_patient_with_overlapping_appointment_then_conflict_at_verify() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)
    patient = make("User", email=VISITOR_EMAIL)
    make(
        "Appointment",
        patient=patient,
        clinician=other,
        appointment_type=clinic.appointment_type,
        starts_at=SLOT,
        ends_at=SLOT + THIRTY_MINUTES,
    )
    hold = _held(clinic)

    result = _verify(hold.pk, _last_code())

    assert result == Failure.conflict(["patient"])
    assert BookingHold.objects.filter(pk=hold.pk).exists()


def returns_rule_violation_and_hold_kept_when_patient_has_three_open_online_bookings() -> None:
    clinic = make_clinic()
    patient = make("User", email=VISITOR_EMAIL)
    for week in range(1, 4):
        start = SLOT + timedelta(weeks=week)
        make(
            "Appointment",
            patient=patient,
            appointment_type=clinic.appointment_type,
            starts_at=start,
            ends_at=start + THIRTY_MINUTES,
        )
    hold = _held(clinic)

    result = _verify(hold.pk, _last_code())

    assert result == Failure.rule_violation(["too_many_open_bookings"])
    assert BookingHold.objects.filter(pk=hold.pk).exists()
    assert Appointment.objects.filter(patient=patient).count() == 3  # type: ignore[misc]


def returns_booking_when_the_slot_is_only_blocked_by_the_visitors_own_hold() -> None:
    hold = _held(make_clinic())

    assert isinstance(_verify(hold.pk, _last_code()), Success)


def returns_audit_of_patient_created_and_booking_with_patient_as_actor() -> None:
    clinic = make_clinic()

    appointment = _booked_by_visitor(clinic, email="vera.visitor@clinic-mail.test")

    patient = User.objects.get(pk=appointment.patient_id)
    created = AuditLogEntry.objects.get(action="user.patient_created")
    booked = AuditLogEntry.objects.get(action="appointment.book")
    assert created.actor_id == patient.pk
    assert created.metadata["email_domain"] == "clinic-mail.test"
    assert booked.actor_id == patient.pk
    assert booked.metadata["email_domain"] == "clinic-mail.test"
    assert AuditLogEntry.objects.filter(action="appointment.book").count() == 1
    for entry in (created, booked):
        assert "vera" not in str(entry.metadata).lower()
        assert VISITOR_NAME not in str(entry.metadata)


def returns_one_confirmation_email_after_commit_when_booked(
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    hold = _held(make_clinic())
    code = _last_code()
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        _verify(hold.pk, code)

    notification = Notification.objects.get(title="Appointment booked")
    assert notification.recipient.email == VISITOR_EMAIL
    assert [message.to for message in mail.outbox] == [[VISITOR_EMAIL]]
    assert "Appointment booked" in mail.outbox[0].subject


def returns_wrong_code_answer_without_booking_when_code_is_wrong() -> None:
    hold = _held(make_clinic())

    _verify(hold.pk, "999999" if _last_code() != "999999" else "888888")

    assert Appointment.objects.count() == 0
    assert VerificationCode.objects.get(hold=hold).attempts_used == 1


def returns_a_hash_comparison_for_a_hold_whose_code_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scheduling.use_cases import booking_codes, booking_verification

    hold = _held(make_clinic())
    VerificationCode.objects.filter(hold=hold).delete()
    comparisons: list[str] = []

    def counting_match(stored_hash: str, hold_id: object, code: str) -> bool:
        comparisons.append(code)
        return booking_codes.code_matches(stored_hash, hold_id, code)  # type: ignore[arg-type]

    monkeypatch.setattr(booking_verification, "code_matches", counting_match)

    answer = _verify(hold.pk, "123456")

    assert answer == booking_verification.INVALID_CODE
    assert comparisons == ["123456"]
