import os

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUE = "true"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ImproperlyConfigured(f"Missing required environment variable {name}")
    return value


def require_env_list(name: str) -> list[str]:
    return [item.strip() for item in require_env(name).split(",") if item.strip()]


def env_flag(name: str) -> bool:
    return os.environ.get(name) == TRUE_VALUE
