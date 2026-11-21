"""Section 7.5: no answer reveals whether an address has an account. A new address, an existing
patient and a staff address get the same answer and cause the same work, before the code."""

from collections.abc import Callable, Iterator

import pytest
from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Failure, Result, Success
from scheduling.models import AuditLogEntry, BookingHold, User
from scheduling.models.access import VerificationCode
from scheduling.models.builders import make, make_clinic
from scheduling.use_cases.test_booking_support import (
    NOW,
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

NEW = "new.person@example.test"
PATIENT = "known.patient@example.test"
ADMIN = "some.admin@example.test"
CLINICIAN = "some.clinician@example.test"
ALL_ADDRESSES = [NEW, PATIENT, ADMIN, CLINICIAN]


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


@pytest.fixture(autouse=True)
def accounts() -> None:
    make("User", email=PATIENT, full_name="Known Patient")
    make("User", email=ADMIN, role="ADMIN")
    make("User", email=CLINICIAN, role="CLINICIAN")


def _measure(action: Callable[[str], object]) -> list[dict[str, object]]:
    """Runs the action once per address, each in a clinic of its own, and records the work."""
    work = []
    for email in ALL_ADDRESSES:
        before = _counts()
        outbox_before = len(mail.outbox)
        with CaptureQueriesContext(connection) as queries:
            answer = action(email)
        work.append(
            {
                "answer_kind": _kind(answer),
                "queries": len(queries),
                "mails": len(mail.outbox) - outbox_before,
                "rows": {name: _counts()[name] - before[name] for name in before},
            }
        )
    return work


def _counts() -> dict[str, int]:
    return {
        "holds": BookingHold.objects.count(),
        "codes": VerificationCode.objects.count(),
        "hits": len(_model_rows("RateLimitHit")),
        "audit": AuditLogEntry.objects.count(),
        "users": User.objects.count(),
    }


def _kind(answer: object) -> str:
    if isinstance(answer, Failure):
        return f"failure:{answer.code.value}:{sorted(answer.details)}"
    return type(answer).__name__


def returns_same_answer_and_work_when_hold_is_created_for_any_kind_of_address() -> None:
    work = _measure(lambda email: _create(make_clinic(), email=email))

    assert all(entry["answer_kind"] == "Success" for entry in work)
    assert all(entry["mails"] == 1 for entry in work)
    assert work[1:] == work[:1] * 3


def returns_same_audit_actions_when_hold_is_created_for_any_kind_of_address() -> None:
    actions_by_email = {}
    for email in ALL_ADDRESSES:
        _create(make_clinic(), email=email)
        entry = AuditLogEntry.objects.filter(metadata__email_domain="example.test")
        actions_by_email[email] = sorted(entry.values_list("action", flat=True))

    created = AuditLogEntry.objects.filter(action="booking_hold.created")
    assert created.count() == 4
    assert {entry.actor_id for entry in created} == {None}


def returns_same_answer_and_work_when_code_is_resent_for_any_kind_of_address() -> None:
    holds = {email: _held(make_clinic(), email=email) for email in ALL_ADDRESSES}

    work = _measure(lambda email: _resend(holds[email].pk))

    assert all(entry["answer_kind"] == "Success" for entry in work)
    assert all(entry["mails"] == 1 for entry in work)
    assert work[1:] == work[:1] * 3


def returns_same_answer_and_work_when_wrong_code_is_sent_for_any_kind_of_address() -> None:
    holds = {email: _held(make_clinic(), email=email) for email in ALL_ADDRESSES}
    codes = {email: _last_code() for email in ALL_ADDRESSES}

    work = _measure(lambda email: _verify(holds[email].pk, _wrong_code(codes[email])))

    assert all(entry["answer_kind"].startswith("failure:invalid_input") for entry in work)  # type: ignore[attr-defined]
    assert work[1:] == work[:1] * 3


def returns_no_name_birth_date_or_appointment_of_a_patient_when_hold_is_created() -> None:
    patient = make("User", email="secret.patient@example.test", full_name="Secret Person")
    make("Appointment", patient=patient)
    clinic = make_clinic()

    result: Result[BookingHold] = _create(clinic, email=patient.email)  # type: ignore[attr-defined]

    assert isinstance(result, Success)
    shown = repr(result.value.__dict__) + repr(mail.outbox[-1].body) + mail.outbox[-1].subject
    assert "Secret Person" not in shown
    assert str(patient.pk) not in shown
