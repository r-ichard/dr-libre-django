import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = REPOSITORY_ROOT / "scripts" / "audit.sh"
SHELL = "/bin/sh"
UV_STUB_LINES = [
    "#!/bin/sh",
    'echo "$*" >> "$AUDIT_LOG"',
    'case "$1" in',
    '  export) exit "$STUB_EXPORT_EXIT" ;;',
    '  run) exit "$STUB_AUDIT_EXIT" ;;',
    "esac",
    "exit 99",
]


def _run_audit(
    tmp_path: Path, export_exit: int, audit_exit: int
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    stub_directory = tmp_path / "bin"
    stub_directory.mkdir()
    stub_uv = stub_directory / "uv"
    stub_uv.write_text("\n".join(UV_STUB_LINES) + "\n")
    stub_uv.chmod(0o755)
    audit_log = tmp_path / "uv.log"
    environment = {
        **os.environ,
        "PATH": f"{stub_directory}{os.pathsep}{os.environ['PATH']}",
        "AUDIT_LOG": str(audit_log),
        "STUB_EXPORT_EXIT": str(export_exit),
        "STUB_AUDIT_EXIT": str(audit_exit),
    }
    result = subprocess.run(  # noqa: S603
        [SHELL, str(AUDIT_SCRIPT)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    logged_lines = audit_log.read_text().splitlines() if audit_log.exists() else []
    return result, logged_lines


def returns_failure_when_pip_audit_reports_a_vulnerability(tmp_path: Path) -> None:
    result, _ = _run_audit(tmp_path, export_exit=0, audit_exit=1)

    assert result.returncode == 1


def returns_success_when_pip_audit_reports_no_vulnerability(tmp_path: Path) -> None:
    result, _ = _run_audit(tmp_path, export_exit=0, audit_exit=0)

    assert result.returncode == 0


def returns_export_failure_without_auditing_when_uv_export_fails(tmp_path: Path) -> None:
    # 3, not 2: sh exits 2 when the script is missing, which must not pass as an export failure.
    result, logged_lines = _run_audit(tmp_path, export_exit=3, audit_exit=0)

    assert result.returncode == 3
    assert any(line.startswith("export ") for line in logged_lines)
    assert not [line for line in logged_lines if line.startswith("run ")]


def returns_hashed_locked_requirements_to_pip_audit_when_run(tmp_path: Path) -> None:
    _, logged_lines = _run_audit(tmp_path, export_exit=0, audit_exit=0)

    assert "export --locked --no-emit-project --format requirements-txt" in logged_lines
    assert any(
        line.startswith("run pip-audit --require-hashes --disable-pip -r ") for line in logged_lines
    )
