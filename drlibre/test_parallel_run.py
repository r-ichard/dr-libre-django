import subprocess
import sys
from pathlib import Path

from pytest_django.fixtures import Settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_parallel_pytest(tmp_path: Path, module_source: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "test_sample.py").write_text(module_source)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-n",
        "2",
        "-p",
        "conftest",
        "-p",
        "no:cacheprovider",
        "-o",
        "python_functions=returns_*",
        str(tmp_path),
    ]
    environment = {"PYTHONPATH": str(PROJECT_ROOT), "PATH": "/usr/bin:/bin"}
    return subprocess.run(  # noqa: S603
        command, cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60
    )


def returns_nonzero_exit_and_names_function_when_parallel_run_meets_uncollected_test(
    tmp_path: Path,
) -> None:
    result = _run_parallel_pytest(tmp_path, "def checks_x():\n    pass\n")

    assert result.returncode != 0
    assert "checks_x" in result.stdout + result.stderr


def returns_nonzero_exit_when_parallel_run_has_failing_test(tmp_path: Path) -> None:
    result = _run_parallel_pytest(tmp_path, "def returns_x():\n    assert False\n")

    assert result.returncode != 0
    assert "1 failed" in result.stdout


def returns_md5_hash_when_test_makes_password(settings: Settings) -> None:
    from django.contrib.auth.hashers import make_password

    assert make_password("any-password").startswith("md5$")
