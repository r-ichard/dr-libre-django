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


def optional_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_whole_count(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        count = int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a whole number") from None
    if count < 0:
        raise ImproperlyConfigured(f"{name} must not be negative")
    return count
