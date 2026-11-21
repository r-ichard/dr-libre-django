from drlibre import settings


def returns_environment_values_when_settings_are_loaded() -> None:
    assert settings.ALLOWED_HOSTS[:2] == ["localhost", "127.0.0.1"]
    assert settings.MAILERS["default"]["OPTIONS"] == {"host": "localhost", "port": 1025}
