import importlib
from collections.abc import Iterator

import pytest

from drlibre import settings


@pytest.fixture
def reloaded_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield
    monkeypatch.undo()
    importlib.reload(settings)


def returns_environment_values_when_settings_are_loaded(
    monkeypatch: pytest.MonkeyPatch, reloaded_settings: None
) -> None:
    monkeypatch.setenv("EMAIL_HOST", "mail-example")
    monkeypatch.setenv("EMAIL_PORT", "2525")
    monkeypatch.setenv("ALLOWED_HOSTS", "a.example,b.example")

    importlib.reload(settings)

    assert settings.ALLOWED_HOSTS == ["a.example", "b.example"]
    assert settings.MAILERS["default"]["OPTIONS"] == {
        "host": "mail-example",
        "port": 2525,
        "timeout": 10,
    }


def returns_default_pbkdf2_hasher_when_product_settings_are_loaded() -> None:
    from django.conf import global_settings

    product_hashers = getattr(settings, "PASSWORD_HASHERS", global_settings.PASSWORD_HASHERS)

    assert product_hashers[0] == "django.contrib.auth.hashers.PBKDF2PasswordHasher"
