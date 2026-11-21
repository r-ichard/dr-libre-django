"""Sections 7.1 steps 5 and 6, 7.2, 7.7: the right code books the held slot for the patient the
email identifies, in one transaction; a failed placing keeps the hold and creates nothing. A wrong,
expired or used-up code gets one answer."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction

from scheduling.domain.audit_metadata import AuditMetadata, email_domain
from scheduling.domain.booking_codes import MAXIMUM_ATTEMPTS, code_is_usable
from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.vocabulary import AppointmentSource, Role, SessionKind
from scheduling.models import Appointment, BookingHold, User, VerificationCode
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.booking_codes import code_matches
from scheduling.use_cases.placement import HoldClaim, PlacementCommand, place_appointment
from scheduling.use_cases.request_context import current_request_context
from scheduling.use_cases.session import open_session

INVALID_CODE = Failure.invalid_input([FieldMessage("code", "The code is not valid.")])
NO_CODE_HASH = "0" * 64


@dataclass(frozen=True)
class VerifiedBooking:
    appointment: Appointment
    token: str
    session_expires_at: datetime


def verify_hold(hold_id: UUID, code: str, user_agent: str) -> Result[VerifiedBooking]:
    now = current_request_context().now
    with transaction.atomic():
        hold = (
            BookingHold.objects.select_for_update().filter(pk=hold_id, expires_at__gt=now).first()
        )
        if hold is None:
            return Failure.not_found()
        stored = VerificationCode.objects.select_for_update().filter(hold=hold).first()
        if not _code_accepted(hold, stored, code, now):
            _record_failed_attempt(hold, stored)
            return INVALID_CODE
        # The failed-attempt rule stops here: from now on a failure leaves the code as it was.
        with transaction.atomic():
            booked = _book_for_visitor(hold, user_agent)
            if isinstance(booked, Failure):
                transaction.set_rollback(True)
                return booked
            if stored is not None:
                stored.delete()
            hold.delete()
        return booked


def _code_accepted(
    hold: BookingHold, stored: VerificationCode | None, code: str, now: datetime
) -> bool:
    # The hash is compared even when the code is unusable, so every answer costs the same work.
    matches = code_matches(stored.code_hash if stored else NO_CODE_HASH, hold.pk, code)
    return (
        stored is not None
        and code_is_usable(stored.expires_at, stored.attempts_used, now)
        and matches
    )


def _record_failed_attempt(hold: BookingHold, stored: VerificationCode | None) -> None:
    if stored is not None and stored.attempts_used < MAXIMUM_ATTEMPTS:
        stored.attempts_used += 1
        stored.save(update_fields=["attempts_used", "updated_at"])
    attempts = stored.attempts_used if stored is not None else 0
    metadata = AuditMetadata(
        counts={"attempt_count": attempts}, email_domain=email_domain(hold.visitor_email)
    )
    event = AuditEvent("booking_code.verification_failed", "BookingHold", str(hold.pk), metadata)
    record_audit(event, None)


def _book_for_visitor(hold: BookingHold, user_agent: str) -> Result[VerifiedBooking]:
    patient = _patient_of(hold)
    if isinstance(patient, Failure):
        return patient
    claim = HoldClaim(hold.pk, AppointmentSource(hold.source), email_domain(hold.visitor_email))
    command = PlacementCommand(
        hold.appointment_type_id,
        hold.starts_at,
        hold.clinician_id,
        None,
        None,
        reason=hold.visitor_reason,
        via_hold=claim,
    )
    placed = place_appointment(command, patient.value)
    if isinstance(placed, Failure):
        return placed
    opened = open_session(patient.value, SessionKind.BOOKING_CODE, user_agent)
    return Success(VerifiedBooking(placed.value, opened.token, opened.session.expires_at))


def _patient_of(hold: BookingHold) -> Result[User]:
    """An active patient keeps their profile. Staff and inactive users get the generic refusal.
    The user row is not locked here: placing locks clinicians, then the patient, then rooms, and
    a lock taken earlier would reverse that order."""
    existing = User.objects.filter(email=hold.visitor_email).first()
    if existing is not None:
        if existing.role == Role.PATIENT and existing.is_active:
            return Success(existing)
        return Failure.forbidden()
    now = current_request_context().now
    patient = User(
        email=hold.visitor_email,
        full_name=hold.visitor_name,
        role=Role.PATIENT,
        phone=hold.visitor_phone,
        date_of_birth=hold.visitor_birth_date,
        email_verified_at=now,
        terms_accepted_at=hold.terms_accepted_at,
    )
    patient.set_unusable_password()
    patient.save()
    metadata = AuditMetadata(
        ids={"patient_id": patient.pk}, email_domain=email_domain(hold.visitor_email)
    )
    record_audit(AuditEvent("user.patient_created", "User", str(patient.pk), metadata), patient)
    return Success(patient)
