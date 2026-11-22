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


def returns_proxy_ssl_header_none_when_trusted_proxy_count_is_unset(
    monkeypatch: pytest.MonkeyPatch, reloaded_settings: None
) -> None:
    monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)

    importlib.reload(settings)

    assert settings.SECURE_PROXY_SSL_HEADER is None
    assert settings.TRUSTED_PROXY_COUNT == 0


def returns_proxy_ssl_header_when_count_is_one(
    monkeypatch: pytest.MonkeyPatch, reloaded_settings: None
) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

    importlib.reload(settings)

    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert settings.TRUSTED_PROXY_COUNT == 1


def raises_improperly_configured_naming_trusted_proxy_count_when_not_a_number(
    monkeypatch: pytest.MonkeyPatch, reloaded_settings: None
) -> None:
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "many")

    with pytest.raises(ImproperlyConfigured, match="TRUSTED_PROXY_COUNT"):
        importlib.reload(settings)


def raises_improperly_configured_naming_trusted_proxy_count_when_negative(
    monkeypatch: pytest.MonkeyPatch, reloaded_settings: None
) -> None:
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "-1")

    with pytest.raises(ImproperlyConfigured, match="TRUSTED_PROXY_COUNT"):
        importlib.reload(settings)
