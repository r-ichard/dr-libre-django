"""Section 7.1 steps 3 and 4, 7.6, 7.7: holding a slot for a visitor and sending the code."""

from collections.abc import Iterator, Sequence
from datetime import date, datetime, timedelta

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.db.models import F

from scheduling.domain.failure import Failure, FieldMessage, Success
from scheduling.models import Appointment, AuditLogEntry, BookingHold, ClinicianProfile
from scheduling.models.access import VerificationCode
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.use_cases.test_booking_support import (
    NOW,
    SLOT,
    TEN_MINUTES,
    THIRTY_MINUTES,
    VISITOR_BIRTH_DATE,
    VISITOR_EMAIL,
    VISITOR_NAME,
    VISITOR_PHONE,
    _at,
    _create,
    _held,
    _last_code,
    _model_rows,
    _resend,
    _verify,
    _wrong_code,
)

pytestmark = pytest.mark.django_db


class MailServerDownBackend(BaseEmailBackend):
    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        raise ConnectionRefusedError("mail server down")


def _assigned_at(clinician: ClinicianProfile, instant: datetime) -> None:
    ClinicianProfile.objects.filter(pk=clinician.pk).update(
        last_assigned_at=instant, version=F("version") + 1
    )


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def returns_hold_for_ten_minutes_when_slot_is_free() -> None:
    clinic = make_clinic()

    hold = _held(clinic, email="  Vera.Visitor@Example.TEST ", reason="Sore knee")

    assert hold.clinician_id == clinic.clinician.pk
    assert hold.appointment_type_id == clinic.appointment_type.pk
    assert (hold.starts_at, hold.ends_at) == (SLOT, SLOT + THIRTY_MINUTES)
    assert hold.expires_at == NOW + TEN_MINUTES
    assert hold.source == "ONLINE"
    assert hold.visitor_email == "vera.visitor@example.test"
    assert (hold.visitor_name, hold.visitor_phone) == (VISITOR_NAME, VISITOR_PHONE)
    assert hold.visitor_birth_date == VISITOR_BIRTH_DATE
    assert hold.visitor_reason == "Sore knee"


def returns_terms_time_equal_to_now_when_terms_are_accepted() -> None:
    hold = _held(make_clinic())

    assert hold.terms_accepted_at == NOW


def returns_invalid_input_and_no_hold_when_terms_are_not_accepted() -> None:
    result = _create(make_clinic(), terms_accepted=False)

    message = FieldMessage("terms_accepted", "Accept the terms and the privacy notice.")
    assert result == Failure.invalid_input([message])
    assert BookingHold.objects.count() == 0
    assert mail.outbox == []


@pytest.mark.parametrize("birth_date", [date(2030, 1, 8), date(1900, 1, 1)])
def returns_invalid_input_when_birth_date_is_impossible(birth_date: date) -> None:
    result = _create(make_clinic(), birth_date=birth_date)

    assert isinstance(result, Failure)
    assert result.details["fields"][0]["field"] == "date_of_birth"  # type: ignore[index]
    assert BookingHold.objects.count() == 0


def returns_rule_violation_and_no_hold_when_lead_time_is_short() -> None:
    clinic = make_clinic()

    with _at(SLOT - timedelta(hours=1)):
        result = _create(clinic)

    assert result == Failure.rule_violation(["lead_time_too_short"])
    assert BookingHold.objects.count() == 0
    assert mail.outbox == []


def returns_conflict_and_no_hold_when_clinician_is_busy() -> None:
    clinic = make_clinic()
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        starts_at=SLOT,
        ends_at=SLOT + THIRTY_MINUTES,
    )

    result = _create(clinic)

    assert result == Failure.conflict(["clinician"])
    assert BookingHold.objects.count() == 0


def returns_not_found_when_type_is_not_bookable_online() -> None:
    clinic = make_clinic(type_fields={"is_bookable_online": False})

    assert _create(clinic) == Failure.rule_violation(["type_not_bookable_online"])
    assert BookingHold.objects.count() == 0


def returns_clinician_never_assigned_when_none_named_and_one_was_assigned_lately() -> None:
    clinic = make_clinic()
    _assigned_at(clinic.clinician, NOW - timedelta(hours=1))
    fresh = add_clinician(clinic.department)

    hold = _held(clinic, clinician_id=None)

    assert hold.clinician_id == fresh.pk
    assert hold.source == "ROUND_ROBIN"


def returns_clinician_assigned_longest_ago_when_none_named() -> None:
    clinic = make_clinic()
    _assigned_at(clinic.clinician, NOW - timedelta(hours=1))
    long_ago = add_clinician(clinic.department)
    _assigned_at(long_ago, NOW - timedelta(hours=3))

    hold = _held(clinic, clinician_id=None)

    assert hold.clinician_id == long_ago.pk


def returns_no_clinician_available_when_none_named_and_all_are_busy() -> None:
    clinic = make_clinic()
    make(
        "Appointment",
        appointment_type=clinic.appointment_type,
        clinician=clinic.clinician,
        starts_at=SLOT,
        ends_at=SLOT + THIRTY_MINUTES,
    )

    result = _create(clinic, clinician_id=None)

    assert result == Failure.no_clinician_available()
    assert BookingHold.objects.count() == 0


def returns_one_hold_and_audit_replaced_when_same_email_holds_again() -> None:
    clinic = make_clinic()
    first = _held(clinic)

    second = _held(clinic, starts_at=SLOT + timedelta(hours=1), email=VISITOR_EMAIL.upper())

    assert list(BookingHold.objects.values_list("pk", flat=True)) == [second.pk]
    assert AuditLogEntry.objects.filter(action="booking_hold.replaced").count() == 1
    assert _verify(first.pk, _last_code()) == Failure.not_found()


def returns_old_code_invalid_when_same_email_holds_again() -> None:
    clinic = make_clinic()
    _held(clinic)
    old_code = _last_code()
    second = _held(clinic, starts_at=SLOT + timedelta(hours=1))

    result = _verify(second.pk, old_code if old_code != _last_code() else _wrong_code(old_code))

    assert result == Failure.invalid_input([FieldMessage("code", "The code is not valid.")])


def returns_expired_hold_removed_and_audited_when_same_email_holds_again() -> None:
    clinic = make_clinic()
    stale = make(
        "BookingHold",
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        visitor_email=VISITOR_EMAIL,
        expires_at=NOW - timedelta(seconds=1),
    )

    fresh = _held(clinic)

    assert not BookingHold.objects.filter(pk=stale.pk).exists()
    assert BookingHold.objects.filter(pk=fresh.pk).exists()
    assert AuditLogEntry.objects.filter(action="booking_hold.expired").count() == 1
    assert AuditLogEntry.objects.filter(action="booking_hold.replaced").count() == 0


def returns_hashed_code_valid_ten_minutes_when_hold_is_created() -> None:
    hold = _held(make_clinic())

    code_row = VerificationCode.objects.get(hold=hold)
    assert code_row.code_hash != _last_code()
    assert len(code_row.code_hash) == 64
    assert _last_code() not in code_row.code_hash
    assert code_row.email == VISITOR_EMAIL
    assert code_row.purpose == "BOOKING"
    assert code_row.expires_at == NOW + TEN_MINUTES
    assert code_row.attempts_used == 0


def returns_one_code_email_with_no_link_when_hold_is_created() -> None:
    _held(make_clinic())

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [VISITOR_EMAIL]
    assert len(_last_code()) == 6
    assert "http" not in mail.outbox[0].body


def returns_audit_with_no_actor_and_email_domain_only_when_hold_is_created() -> None:
    hold = _held(make_clinic(), email="vera.visitor@clinic-mail.test")

    entry = AuditLogEntry.objects.get(action="booking_hold.created")
    assert entry.actor_id is None
    assert entry.entity_id == str(hold.pk)
    assert entry.metadata["email_domain"] == "clinic-mail.test"
    assert "vera" not in str(entry.metadata).lower()
    assert VISITOR_NAME not in str(entry.metadata)


def returns_new_code_and_old_code_invalid_when_code_is_resent() -> None:
    hold = _held(make_clinic())
    old_code = _last_code()

    result = _resend(hold.pk)

    assert isinstance(result, Success)
    assert len(mail.outbox) == 2
    new_code = _last_code()
    assert _verify(hold.pk, old_code if old_code != new_code else _wrong_code(new_code)) == (
        Failure.invalid_input([FieldMessage("code", "The code is not valid.")])
    )


def returns_not_found_when_resending_for_unknown_or_expired_hold() -> None:
    clinic = make_clinic()
    hold = _held(clinic)

    with _at(NOW + TEN_MINUTES):
        expired = _resend(hold.pk)
    unknown = _resend("00000000-0000-4000-8000-000000000000")

    assert expired == Failure.not_found()
    assert unknown == Failure.not_found()


def returns_rate_limited_on_fourth_resend_and_success_after_an_hour() -> None:
    hold = _held(make_clinic())
    BookingHold.objects.filter(pk=hold.pk).update(
        expires_at=NOW + timedelta(days=1), version=F("version") + 1
    )

    first_three = [_resend(hold.pk) for _ in range(3)]
    fourth = _resend(hold.pk)
    with _at(NOW + timedelta(minutes=61)):
        later = _resend(hold.pk)

    assert all(isinstance(result, Success) for result in first_three)
    assert fourth == Failure.rate_limited()
    assert isinstance(later, Success)
    assert len(mail.outbox) == 1 + 3 + 1


def returns_invalid_even_for_right_code_when_five_wrong_attempts_were_used() -> None:
    hold = _held(make_clinic())
    right = _last_code()
    invalid = Failure.invalid_input([FieldMessage("code", "The code is not valid.")])

    wrong_answers = [_verify(hold.pk, _wrong_code(right)) for _ in range(5)]
    sixth = _verify(hold.pk, right)

    assert wrong_answers == [invalid] * 5
    assert sixth == invalid
    assert VerificationCode.objects.get(hold=hold).attempts_used == 5


def returns_right_new_code_working_when_resend_follows_five_wrong_attempts() -> None:
    hold = _held(make_clinic())
    for _ in range(5):
        _verify(hold.pk, _wrong_code(_last_code()))

    _resend(hold.pk)

    assert VerificationCode.objects.get(hold=hold).attempts_used == 0
    assert isinstance(_verify(hold.pk, _last_code()), Success)


def returns_audit_without_actor_when_code_verification_fails() -> None:
    hold = _held(make_clinic(), email="vera.visitor@clinic-mail.test")

    _verify(hold.pk, _wrong_code(_last_code()))

    entry = AuditLogEntry.objects.get(action="booking_code.verification_failed")
    assert entry.actor_id is None
    assert entry.metadata["email_domain"] == "clinic-mail.test"
    assert "vera" not in str(entry.metadata).lower()


def returns_no_hold_code_or_hit_when_mail_server_is_down_on_hold(settings: object) -> None:
    clinic = make_clinic()
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.MailServerDownBackend", "OPTIONS": {}}
    }

    assert _create(clinic) == Failure.mail_unavailable()

    assert BookingHold.objects.count() == 0
    assert _model_rows("VerificationCode") == []
    assert _model_rows("RateLimitHit") == []
    assert AuditLogEntry.objects.filter(action="booking_hold.created").count() == 0


def returns_earlier_code_valid_when_mail_server_is_down_on_resend(settings: object) -> None:
    hold = _held(make_clinic())
    earlier = _last_code()
    working = settings.MAILERS  # type: ignore[attr-defined]
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": f"{__name__}.MailServerDownBackend", "OPTIONS": {}}
    }

    assert _resend(hold.pk) == Failure.mail_unavailable()

    settings.MAILERS = working  # type: ignore[attr-defined]
    assert isinstance(_verify(hold.pk, earlier), Success)
    assert Appointment.objects.count() == 1
