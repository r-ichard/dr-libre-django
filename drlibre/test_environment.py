import pytest
from django.core.exceptions import ImproperlyConfigured

from drlibre.environment import env_flag, require_env, require_env_list


def raises_improperly_configured_naming_variable_when_required_value_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DRLIBRE_MISSING_EXAMPLE", raising=False)

    with pytest.raises(ImproperlyConfigured) as error:
        require_env("DRLIBRE_MISSING_EXAMPLE")

    assert str(error.value) == "Missing required environment variable DRLIBRE_MISSING_EXAMPLE"


def returns_value_when_required_variable_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRLIBRE_PRESENT_EXAMPLE", "present-value")

    assert require_env("DRLIBRE_PRESENT_EXAMPLE") == "present-value"


def returns_false_when_flag_variable_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DRLIBRE_FLAG_EXAMPLE", raising=False)

    assert env_flag("DRLIBRE_FLAG_EXAMPLE") is False


def returns_true_only_when_flag_variable_is_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRLIBRE_FLAG_EXAMPLE", "true")
    assert env_flag("DRLIBRE_FLAG_EXAMPLE") is True

    monkeypatch.setenv("DRLIBRE_FLAG_EXAMPLE", "yes")
    assert env_flag("DRLIBRE_FLAG_EXAMPLE") is False


def returns_trimmed_items_when_list_variable_is_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DRLIBRE_LIST_EXAMPLE", "localhost, web ,,127.0.0.1")

    assert require_env_list("DRLIBRE_LIST_EXAMPLE") == ["localhost", "web", "127.0.0.1"]


def returns_default_when_optional_variable_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from drlibre import environment

    monkeypatch.delenv("DRLIBRE_OPTIONAL_EXAMPLE", raising=False)

    assert environment.optional_env("DRLIBRE_OPTIONAL_EXAMPLE", "fallback") == "fallback"


def returns_value_when_optional_variable_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from drlibre import environment

    monkeypatch.setenv("DRLIBRE_OPTIONAL_EXAMPLE", "given")

    assert environment.optional_env("DRLIBRE_OPTIONAL_EXAMPLE", "fallback") == "given"


def raises_improperly_configured_naming_variable_when_count_is_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from drlibre import environment

    monkeypatch.setenv("DRLIBRE_COUNT_EXAMPLE", "-1")

    with pytest.raises(ImproperlyConfigured, match="DRLIBRE_COUNT_EXAMPLE"):
        environment.env_whole_count("DRLIBRE_COUNT_EXAMPLE", 0)
