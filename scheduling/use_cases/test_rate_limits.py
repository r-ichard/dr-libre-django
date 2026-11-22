"""Section 7.5: holds and code requests are limited per email address and per network address,
and the counters hold no readable address."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from django.core import mail

from scheduling.domain.failure import Failure, Success
from scheduling.models import BookingHold
from scheduling.models.builders import add_clinician, make_clinic
from scheduling.use_cases.test_booking_support import (
    ADDRESS,
    NOW,
    VISITOR_EMAIL,
    _at,
    _create,
    _held,
    _model_rows,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def returns_rate_limited_on_sixth_hold_of_one_email_in_an_hour() -> None:
    clinic = make_clinic()

    answers = [_create(clinic, address=f"198.51.100.{number}") for number in range(6)]

    assert all(isinstance(answer, Success) for answer in answers[:5])
    assert answers[5] == Failure.rate_limited()


def returns_hold_again_when_the_hour_has_passed() -> None:
    clinic = make_clinic()
    for number in range(5):
        _create(clinic, address=f"198.51.100.{number}")

    with _at(NOW + timedelta(minutes=61)):
        answer = _create(clinic, address="198.51.100.99")

    assert isinstance(answer, Success)


def returns_rate_limited_on_twenty_first_hold_from_one_network_address() -> None:
    clinic = make_clinic()
    for _ in range(21):
        add_clinician(clinic.department)

    answers = [
        _create(clinic, clinician_id=None, email=f"visitor.{number}@example.test")
        for number in range(21)
    ]

    assert all(isinstance(answer, Success) for answer in answers[:20])
    assert answers[20] == Failure.rate_limited()


def returns_hold_when_another_network_address_asks_after_the_first_is_full() -> None:
    clinic = make_clinic()
    for _ in range(21):
        add_clinician(clinic.department)
    for number in range(20):
        _create(clinic, clinician_id=None, email=f"visitor.{number}@example.test")

    answer = _create(
        clinic, clinician_id=None, email="other.visitor@example.test", address="198.51.100.200"
    )

    assert isinstance(answer, Success)


def returns_same_limit_for_one_email_in_other_letter_case() -> None:
    clinic = make_clinic()
    for number in range(5):
        _create(clinic, address=f"198.51.100.{number}", email=VISITOR_EMAIL.upper())

    answer = _create(clinic, address="198.51.100.50", email=VISITOR_EMAIL)

    assert answer == Failure.rate_limited()


def returns_no_hold_and_no_mail_when_request_is_refused() -> None:
    clinic = make_clinic()
    for number in range(5):
        _create(clinic, address=f"198.51.100.{number}")
    mails_before = len(mail.outbox)
    hits_before = len(_model_rows("RateLimitHit"))

    _create(clinic, address="198.51.100.77", email=VISITOR_EMAIL)
    refused = _create(clinic, address="198.51.100.78", email=VISITOR_EMAIL)

    assert refused == Failure.rate_limited()
    assert len(mail.outbox) == mails_before
    assert len(_model_rows("RateLimitHit")) == hits_before
    assert BookingHold.objects.count() == 1


def returns_hashes_without_the_email_or_the_address_when_a_hold_is_created() -> None:
    _held(make_clinic())

    rows = _model_rows("RateLimitHit")
    assert len(rows) == 2
    for row in rows:
        assert row.scope == "hold"  # type: ignore[attr-defined]
        assert len(row.key_hash) == 64  # type: ignore[attr-defined]
        shown = str(row.__dict__).lower()
        assert VISITOR_EMAIL not in shown
        assert "visitor" not in shown
        assert ADDRESS not in shown
    assert len({row.key_hash for row in rows}) == 2  # type: ignore[attr-defined]


def returns_same_hash_for_the_same_email_on_two_requests() -> None:
    clinic = make_clinic()
    _held(clinic)
    _held(clinic)

    hashes = [row.key_hash for row in _model_rows("RateLimitHit")]  # type: ignore[attr-defined]
    assert len(hashes) == 4
    assert len(set(hashes)) == 2


def returns_longer_wait_when_email_and_address_counters_are_both_full() -> None:
    from scheduling.domain.rate_limit_rules import RateLimitScope
    from scheduling.models import RateLimitHit
    from scheduling.use_cases.rate_limits import key_hash, take_hit

    email_full_at = NOW - timedelta(minutes=10)
    address_full_at = NOW - timedelta(minutes=50)
    rows = [
        RateLimitHit(
            scope="hold", key_hash=key_hash("email", "a@example.test"), hit_at=email_full_at
        )
        for _ in range(5)
    ] + [
        RateLimitHit(scope="hold", key_hash=key_hash("address", ADDRESS), hit_at=address_full_at)
        for _ in range(20)
    ]
    RateLimitHit.objects.bulk_create(rows)

    wait = take_hit(RateLimitScope.HOLD, "a@example.test", ADDRESS)

    assert wait == 3000
