"""Task 10a: a warning raised in any test fails the suite, so the next one is caught early."""

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def returns_error_filter_when_pytest_is_configured() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())

    filters = config["tool"]["pytest"]["ini_options"].get("filterwarnings")

    assert filters == ["error"]


def returns_clean_compile_when_every_module_is_compiled_with_warnings_as_errors() -> None:
    command = [
        sys.executable,
        "-W",
        "error",
        "-m",
        "compileall",
        "-q",
        "-f",
        "scheduling",
        "drlibre",
    ]

    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603

    assert result.returncode == 0, result.stdout + result.stderr
