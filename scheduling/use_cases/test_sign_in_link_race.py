"""Section 7.3: two requests that post the same link together open exactly one session."""

from collections.abc import Callable
from threading import Barrier, Thread

import pytest
from django.db import connections

from scheduling.domain.failure import Failure, Result, Success
from scheduling.models import Session
from scheduling.use_cases.test_sign_in_link_support import (
    NOW,
    REFUSAL,
    _at,
    _patient,
    _stored_link,
    _use,
)

pytestmark = pytest.mark.django_db(transaction=True)

TOKEN = "planted-token-abcdefghijklmnopqrstuvwxyz"  # noqa: S105 - a planted test value


def _run_together(work: list[Callable[[], Result[object]]]) -> list[Result[object]]:
    barrier = Barrier(len(work))
    results: list[Result[object] | None] = [None] * len(work)

    def worker(index: int) -> None:
        try:
            barrier.wait()
            with _at(NOW):
                results[index] = work[index]()
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=(index,)) for index in range(len(work))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert None not in results
    return [result for result in results if result is not None]


@pytest.mark.parametrize("attempt", range(10))
def returns_one_session_and_one_refusal_when_two_threads_post_the_same_link(
    committed_rows: None, attempt: int
) -> None:
    _stored_link(TOKEN, _patient())

    results = _run_together([lambda: _use(TOKEN), lambda: _use(TOKEN)])

    assert sum(isinstance(result, Success) for result in results) == 1
    assert [result for result in results if isinstance(result, Failure)] == [REFUSAL]
    assert Session.objects.count() == 1
