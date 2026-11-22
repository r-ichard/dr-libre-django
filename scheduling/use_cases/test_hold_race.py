"""Task 26 item 3a, task 26a2 item 5: the hold counter (five an hour for one email address) and the
resend counter (three an hour) are serialised, as the sign-in counter is."""

import pytest

from scheduling.domain.failure import Failure
from scheduling.models.builders import make_clinic
from scheduling.use_cases.test_booking_support import ADDRESS, NOW, _at, _create, _held, _resend
from scheduling.use_cases.test_sign_in_race import _run_together

pytestmark = pytest.mark.django_db(transaction=True)

HOLDS_PER_HOUR = 5
RESENDS_PER_HOUR = 3
THREADS = 10


def _limited(result: object) -> bool:
    return isinstance(result, Failure) and result.code == "rate_limited"


@pytest.mark.parametrize("attempt", range(5))
def returns_five_holds_at_most_when_ten_threads_hold_for_one_email(
    committed_rows: None, attempt: int
) -> None:
    clinic = make_clinic()

    results = _run_together(lambda _index: _create(clinic, ADDRESS), THREADS)

    assert len([result for result in results if not _limited(result)]) == HOLDS_PER_HOUR


@pytest.mark.parametrize("attempt", range(5))
def returns_three_resends_at_most_when_ten_threads_resend_one_hold(
    committed_rows: None, attempt: int
) -> None:
    with _at(NOW):
        hold = _held(make_clinic())

    results = _run_together(lambda _index: _resend(hold.pk, ADDRESS), THREADS)

    resent = [result for result in results if not _limited(result)]
    assert len(resent) == RESENDS_PER_HOUR
