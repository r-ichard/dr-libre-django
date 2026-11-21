from collections.abc import Iterator

import pytest
from django.db import connection

AUDIT_TABLE = "scheduling_auditlogentry"


@pytest.fixture(scope="module")
def committed_rows(django_db_setup: None, django_db_blocker: object) -> Iterator[None]:
    """For modules with transaction=True: the flush would TRUNCATE the append-only audit table,
    so its trigger is off for the module. Module scope, because a function-scoped fixture is
    torn down before the flush."""
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {AUDIT_TABLE} DISABLE TRIGGER USER")
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {AUDIT_TABLE} ENABLE TRIGGER USER")
