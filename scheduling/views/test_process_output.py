"""Runs requests through the real LOGGING in a child process and reads every byte it writes."""

import json
import os
import subprocess
import sys

CHILD_PROGRAM = "\n".join(
    [
        "import logging",
        "import django",
        "django.setup()",
        "from django.test import Client",
        "from django.test.utils import setup_test_environment",
        "from django.conf import settings",
        "setup_test_environment()",
        'settings.ROOT_URLCONF = "scheduling.views.probe_urls"',
        'settings.ALLOWED_HOSTS = ["testserver"]',
        "client = Client(raise_request_exception=False)",
        'client.get("/api/v1/unknown/jane@example.test?token=x")',
        'client.get("/api/v1/probe/patients/jane@example.test?token=x")',
        'client.get("/api/v1/probe/explode?token=x")',
        'client.get("/pages/explode?token=x")',
        'client.post("/api/v1/probe/write", {"role": "admin"}, content_type="application/json")',
        'server = logging.getLogger("django.server")',
        'server.info(\'"%s" %s %s\', "GET /x?token=x HTTP/1.1", 200, 12)',
    ]
)
REQUEST_COUNT = 5
LEAKS = ("jane@example.test", "/unknown/", "token=x", "?token")


def _run_child() -> str:
    finished = subprocess.run(  # noqa: S603
        [sys.executable, "-c", CHILD_PROGRAM],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "DEBUG": "0"},
    )
    return finished.stdout + finished.stderr


def returns_only_json_lines_when_requests_run_through_real_logging_config() -> None:
    output = _run_child()

    lines = [line for line in output.splitlines() if line.strip()]
    assert lines
    for line in lines:
        assert isinstance(json.loads(line), dict), line


def returns_no_path_segment_query_or_email_when_requests_carry_them() -> None:
    output = _run_child()

    for leak in LEAKS:
        assert leak not in output


def returns_one_request_line_per_request_when_django_server_also_logs() -> None:
    output = _run_child()

    entries = [json.loads(line) for line in output.splitlines() if line.strip()]
    loggers = [entry["logger"] for entry in entries]
    assert loggers.count("drlibre.request") == REQUEST_COUNT
    assert "django.server" not in loggers


def returns_trace_line_with_type_and_correlation_id_when_plain_view_raises() -> None:
    output = _run_child()

    entries = [json.loads(line) for line in output.splitlines() if line.strip()]
    traced = [entry for entry in entries if "exception" in entry]
    assert len([e for e in traced if e["exception"]["type"] == "ValueError"]) == 2
    assert all(entry["correlation_id"] for entry in traced)
    assert "chest pain" not in output
