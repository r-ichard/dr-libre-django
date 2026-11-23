"""Section 4: the email job runs outside any transaction. Needs real commits, so the test
transaction cannot wrap it."""

from datetime import UTC, datetime

import pytest
from django.db import connection

from scheduling.jobs.runner import Job, run_job

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("committed_rows")]

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)


def returns_no_outer_transaction_when_job_declares_none() -> None:
    inside: list[bool] = []

    def record_transaction() -> dict[str, int]:
        inside.append(connection.in_atomic_block)
        return {}

    run_job(Job("mail_job", record_transaction, atomic=False), NOW)
    run_job(Job("db_job", record_transaction), NOW)

    assert inside == [False, True]
