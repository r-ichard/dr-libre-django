"""Task 26b item 1: with DEBUG off, start-up refuses unsafe values with one message."""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _checks() -> ModuleType:
    return importlib.import_module("drlibre.startup_checks")


ROOT = Path(__file__).resolve().parent.parent
CHANGED_KEY = "k7Qx9vT2mWp4Zr8LbN3cYd6HfJs1UaEg5XoVt0RiKwMq2PzBn7CyDl4SeAh9GjFu"  # noqa: S105
HOSTS = ["drlibre.example"]


def _env_example() -> dict[str, str]:
    lines = (ROOT / ".env.example").read_text().splitlines()
    pairs = [line.split("=", 1) for line in lines if line and not line.startswith("#")]
    return {name: value for name, value in pairs}


def returns_secret_key_message_when_debug_off_and_development_key() -> None:
    message = _checks().startup_refusal(False, _checks().PUBLISHED_SECRET_KEY, HOSTS, "")

    assert message is not None
    assert "SECRET_KEY" in message


def returns_allowed_hosts_message_when_debug_off_and_hosts_empty() -> None:
    message = _checks().startup_refusal(False, CHANGED_KEY, [], "")

    assert message is not None
    assert "ALLOWED_HOSTS" in message


def returns_demo_password_message_when_debug_off_and_password_set() -> None:
    message = _checks().startup_refusal(
        False, CHANGED_KEY, HOSTS, _checks().PUBLISHED_DEMO_PASSWORD
    )

    assert message is not None
    assert "DEMO_PASSWORD" in message


def returns_none_when_debug_on_with_development_values() -> None:
    assert (
        _checks().startup_refusal(
            True, _checks().PUBLISHED_SECRET_KEY, [], _checks().PUBLISHED_DEMO_PASSWORD
        )
        is None
    )


def returns_none_when_debug_off_and_values_are_safe() -> None:
    assert _checks().startup_refusal(False, CHANGED_KEY, HOSTS, "") is None


def returns_constants_equal_to_env_example_values() -> None:
    published = _env_example()

    assert published["SECRET_KEY"] == _checks().PUBLISHED_SECRET_KEY
    assert published["DEMO_PASSWORD"] == _checks().PUBLISHED_DEMO_PASSWORD


def _start(**overrides: str) -> subprocess.CompletedProcess[str]:
    inherited = {name: os.environ[name] for name in ("PATH", "HOME", "LANG") if name in os.environ}
    environment = {
        **inherited,
        **_env_example(),
        "DEBUG": "false",
        "SECRET_KEY": CHANGED_KEY,
        "DEMO_PASSWORD": "",
        **overrides,
    }
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=ROOT,
        env={**environment, "DJANGO_SETTINGS_MODULE": "drlibre.settings"},
        capture_output=True,
        text=True,
        check=False,
    )


def returns_failure_naming_each_variable_when_debug_is_off_and_value_is_unsafe() -> None:
    cases = {
        "SECRET_KEY": _start(SECRET_KEY=_checks().PUBLISHED_SECRET_KEY),
        "ALLOWED_HOSTS": _start(ALLOWED_HOSTS=""),
        "DEMO_PASSWORD": _start(DEMO_PASSWORD=_checks().PUBLISHED_DEMO_PASSWORD),
    }

    for name, result in cases.items():
        assert result.returncode != 0, name
        assert name in result.stderr, name


def returns_success_when_debug_is_off_and_values_are_safe() -> None:
    result = _start()

    assert result.returncode == 0, result.stderr
