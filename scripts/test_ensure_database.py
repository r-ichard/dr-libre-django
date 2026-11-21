import pytest

from scripts.ensure_database import build_statements

CLEAN_ENVIRONMENT = {"DB_USER": "role_x", "DB_NAME": "database_x", "DB_PASSWORD": "secret_x"}


def _set_environment(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def raises_system_exit_naming_variable_when_variable_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_environment(monkeypatch, CLEAN_ENVIRONMENT)
    monkeypatch.delenv("DB_USER")

    with pytest.raises(SystemExit) as error:
        build_statements()

    assert str(error.value) == "Missing required environment variable DB_USER"


@pytest.mark.parametrize("unsafe_character", ["'", '"', "\\", "\n", "\r"])
def raises_system_exit_naming_variable_when_value_has_unsafe_character(
    monkeypatch: pytest.MonkeyPatch, unsafe_character: str
) -> None:
    _set_environment(monkeypatch, CLEAN_ENVIRONMENT)
    monkeypatch.setenv("DB_PASSWORD", f"pass{unsafe_character}word")

    with pytest.raises(SystemExit) as error:
        build_statements()

    assert "DB_PASSWORD" in str(error.value)
    assert "pass" not in str(error.value)


def returns_set_lines_with_values_when_values_are_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_environment(monkeypatch, CLEAN_ENVIRONMENT)

    statements = build_statements()

    assert statements.startswith(
        "\\set role 'role_x'\n\\set database 'database_x'\n\\set password 'secret_x'\n"
    )
