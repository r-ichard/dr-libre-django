"""Task 19, item 3: two admins who deactivate each other at the same moment leave one admin."""

from collections.abc import Callable
from threading import Barrier, Thread

import pytest
from django.db import connections

from scheduling.domain.failure import Result, Success
from scheduling.models import User
from scheduling.use_cases.admin_users import deactivate_user
from scheduling.use_cases.test_admin_record_support import _an_admin, _in_context

pytestmark = pytest.mark.django_db(transaction=True)


def _run_together(work: list[Callable[[], Result[object]]]) -> list[Result[object]]:
    barrier = Barrier(len(work))
    results: list[Result[object] | None] = [None] * len(work)

    def worker(index: int) -> None:
        try:
            barrier.wait()
            results[index] = _in_context(work[index])
        finally:
            connections.close_all()

    threads = [Thread(target=worker, args=(index,)) for index in range(len(work))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return [result for result in results if result is not None]


@pytest.mark.parametrize("attempt", range(5))
def returns_one_active_admin_when_two_admins_deactivate_each_other_at_once(
    committed_rows: None, attempt: int
) -> None:
    first, second = _an_admin(), _an_admin()

    results = _run_together(
        [
            lambda: deactivate_user(second.pk, second.version, first),
            lambda: deactivate_user(first.pk, first.version, second),
        ]
    )

    assert len(results) == 2 and sum(isinstance(item, Success) for item in results) == 1
    assert User.objects.filter(pk__in=[first.pk, second.pk], is_active=True).count() == 1
