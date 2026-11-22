"""Section 12.1 and 7.5: the counters hold when requests arrive together. Ten wrong passwords are
evaluated per address and window, however many threads post at once."""

from collections.abc import Callable
from threading import Barrier, Thread

import pytest
from django.contrib.auth.hashers import make_password
from django.db import connections, transaction

from scheduling.domain.booking_codes import MAXIMUM_ATTEMPTS
from scheduling.domain.failure import Failure, Result
from scheduling.models import AuditLogEntry, SignInFailure, User
from scheduling.models.builders import make
from scheduling.use_cases.advisory_lock import lock_keys
from scheduling.use_cases.api_tokens import resolve_token
from scheduling.use_cases.sign_in import hash_email, record_wrong_password, sign_in_with_password
from scheduling.use_cases.sign_in_link import ask_for_link
from scheduling.use_cases.test_booking_support import NOW, _at

pytestmark = pytest.mark.django_db(transaction=True)

EMAIL = "race.patient@example.test"
RIGHT_PHRASE = "correct horse battery staple"
WRONG_PHRASE = "wrong horse battery staple"
LOCKOUT_LIMIT = 10
PARALLEL_ATTEMPTS = 50
LINKS_PER_HOUR = 3
TOKEN_FAILURES_PER_HOUR = 5


def _run_together(work: Callable[[int], Result[object]], count: int) -> list[Result[object]]:
    barrier = Barrier(count)
    results: list[Result[object] | None] = [None] * count

    def worker(index: int) -> None:
        try:
            barrier.wait()
            with _at(NOW):
                results[index] = work(index)
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert None not in results
    return [result for result in results if result is not None]


def _wrong_password(address: str) -> Callable[[int], Result[object]]:
    return lambda _index: sign_in_with_password(address, WRONG_PHRASE, "agent")


@pytest.mark.parametrize("attempt", range(5))
def returns_ten_failures_evaluated_when_fifty_wrong_passwords_arrive_together(
    committed_rows: None, attempt: int
) -> None:
    make("User", email=EMAIL, password=make_password(RIGHT_PHRASE))
    results = _run_together(_wrong_password(EMAIL), PARALLEL_ATTEMPTS)

    assert results == [Failure.unauthenticated()] * PARALLEL_ATTEMPTS
    assert SignInFailure.objects.count() == LOCKOUT_LIMIT
    assert AuditLogEntry.objects.filter(action="auth.login_failed").count() == LOCKOUT_LIMIT


@pytest.mark.parametrize("attempt", range(5))
def returns_ten_failures_stored_when_fifty_wrong_passwords_arrive_for_an_unknown_address(
    committed_rows: None, attempt: int
) -> None:
    _run_together(_wrong_password("nobody.here@example.test"), PARALLEL_ATTEMPTS)

    assert SignInFailure.objects.count() == LOCKOUT_LIMIT


@pytest.mark.parametrize("attempt", range(5))
def returns_three_links_at_most_when_ten_threads_ask_for_a_link(
    committed_rows: None, attempt: int
) -> None:
    make("User", email=EMAIL)

    results = _run_together(lambda _index: ask_for_link(EMAIL, "203.0.113.9"), 10)

    asked = [result for result in results if result != Failure.rate_limited()]
    assert len(asked) == LINKS_PER_HOUR


@pytest.mark.parametrize("attempt", range(5))
def returns_five_failures_counted_when_twenty_threads_present_the_same_bad_token(
    committed_rows: None, attempt: int
) -> None:
    results = _run_together(lambda _index: resolve_token("dlk_wrong", "203.0.113.9"), 20)

    unauthenticated = [result for result in results if result == Failure.unauthenticated()]
    assert len(unauthenticated) == TOKEN_FAILURES_PER_HOUR


@pytest.mark.parametrize("attempt", range(5))
def returns_five_attempts_at_most_when_ten_threads_post_wrong_booking_codes(
    committed_rows: None, attempt: int
) -> None:
    from scheduling.models.access import VerificationCode
    from scheduling.models.builders import make_clinic
    from scheduling.use_cases.test_booking_support import _held, _last_code, _verify, _wrong_code

    with _at(NOW):
        hold = _held(make_clinic())
        wrong = _wrong_code(_last_code())

    _run_together(lambda _index: _verify(hold.pk, wrong), 10)

    assert VerificationCode.objects.get(hold=hold).attempts_used == MAXIMUM_ATTEMPTS


BLOCKED_SECONDS = 0.5


def returns_blocked_until_the_address_lock_is_free_when_change_password_records_a_failure(
    committed_rows: None,
) -> None:
    user = User.objects.get(pk=make("User", email=EMAIL).pk)
    finished = []

    def record() -> None:
        try:
            with _at(NOW):
                record_wrong_password(user)
            finished.append(True)
        finally:
            connections.close_all()

    with transaction.atomic():
        lock_keys([hash_email(EMAIL)])
        thread = Thread(target=record)
        thread.start()
        thread.join(BLOCKED_SECONDS)
        assert finished == []
    thread.join()

    assert finished == [True]
    assert SignInFailure.objects.count() == 1
