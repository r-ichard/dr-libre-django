"""Section 16: deployment checks pass on production-like values, and an
unsafe value (the development key, HTTPS off) fails them."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_SECRET = "k7Qx9vT2mWp4Zr8LbN3cYd6HfJs1UaEg5XoVt0RiKwMq2PzBn7CyDl4SeAh9GjFu"  # noqa: S105
INHERITED_NAMES = ("PATH", "HOME", "LANG")


def _development_values() -> dict[str, str]:
    lines = (ROOT / ".env.example").read_text().splitlines()
    pairs = [line.split("=", 1) for line in lines if line and not line.startswith("#")]
    return {name: value for name, value in pairs}


def _production_environment(**overrides: str) -> dict[str, str]:
    inherited = {name: os.environ[name] for name in INHERITED_NAMES if name in os.environ}
    production = {
        **_development_values(),
        "SECRET_KEY": PRODUCTION_SECRET,
        "ALLOWED_HOSTS": "drlibre.example",
        "DEMO_PASSWORD": "",
        "HTTPS_ONLY": "true",
        "HSTS_SECONDS": "31536000",
    }
    return {**inherited, **production, **overrides}


def _deployment_check(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def returns_zero_exit_when_production_values_are_used() -> None:
    result = _deployment_check(_production_environment())

    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr


def returns_failure_naming_secret_key_when_development_key_is_used() -> None:
    development_key = _development_values()["SECRET_KEY"]

    result = _deployment_check(_production_environment(SECRET_KEY=development_key))

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def returns_failure_when_https_only_is_off() -> None:
    result = _deployment_check(_production_environment(HTTPS_ONLY="false"))

    assert result.returncode != 0


def returns_hsts_and_secure_cookies_values_when_https_only_is_on() -> None:
    script = (
        "import django, json; django.setup(); from django.conf import settings as s; "
        "print(json.dumps([s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS, "
        "s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE]))"
    )
    environment = _production_environment(DJANGO_SETTINGS_MODULE="drlibre.settings")

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout.strip() == "[true, 31536000, true, true]", result.stderr


def returns_no_transport_security_when_https_only_is_off() -> None:
    script = (
        "import django, json; django.setup(); from django.conf import settings as s; "
        "print(json.dumps([s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS, "
        "s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE]))"
    )
    environment = _production_environment(
        DJANGO_SETTINGS_MODULE="drlibre.settings", HTTPS_ONLY="false", HSTS_SECONDS="0"
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout.strip() == "[false, 0, true, true]", result.stderr
