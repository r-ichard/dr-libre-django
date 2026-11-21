import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader

pytestmark = pytest.mark.django_db


def returns_no_pending_changes_when_models_match_migrations() -> None:
    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=0)
    except SystemExit as pending:
        pytest.fail(f"models changed without a migration (exit code {pending.code})")


def returns_eight_schema_migrations_when_loader_reads_the_app() -> None:
    loader = MigrationLoader(None, load=False)
    loader.load_disk()

    names = sorted(name for app, name in loader.disk_migrations if app == "scheduling")

    assert len(names) == 8
    assert names[:2] == ["0001_initial", "0002_audit_log_append_only"]


def returns_btree_gist_installed_when_exclusion_constraints_exist() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_extension WHERE extname = 'btree_gist'")
        row = cursor.fetchone()

    assert row == (1,)


def returns_exclusion_constraints_for_clinician_patient_and_room_when_schema_is_read() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_constraint "
            "WHERE contype = 'x' AND conrelid = 'scheduling_appointment'::regclass"
        )
        row = cursor.fetchone()

    assert row == (3,)


def returns_empty_database_migrated_when_all_migrations_apply_and_reverse() -> None:
    call_command("migrate", "scheduling", "0002", verbosity=0)
    call_command("migrate", "scheduling", verbosity=0)
