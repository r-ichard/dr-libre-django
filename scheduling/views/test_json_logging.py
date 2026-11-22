import json
import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.test import Client

from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views.api_clients import browser_api_client
from scheduling.views.json_logging import JsonFormatter

EMAIL = "a@b.example"
TOKEN = "tok_abc123"  # noqa: S105
NOTE = "patient reports chest pain"
INSTANT = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)


class _CollectingHandler(logging.Handler):
    def __init__(self, lines: list[dict[str, object]]) -> None:
        super().__init__()
        self.lines = lines
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def log_lines() -> Iterator[list[dict[str, object]]]:
    lines: list[dict[str, object]] = []
    handler = _CollectingHandler(lines)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


def _raw_output(stream_lines: list[dict[str, object]]) -> str:
    return json.dumps(stream_lines)


def returns_one_json_object_per_line_with_time_level_logger_message_correlation_id() -> None:
    record = logging.LogRecord("drlibre.demo", logging.WARNING, __file__, 1, "hello", None, None)
    context = RequestContext(correlation_id="cid-1", now=INSTANT)

    with bind_request_context(context):
        line = JsonFormatter().format(record)

    parsed = json.loads(line)
    assert "\n" not in line
    assert set(parsed) == {"time", "level", "logger", "message", "correlation_id"}
    assert (parsed["level"], parsed["logger"], parsed["message"]) == (
        "WARNING",
        "drlibre.demo",
        "hello",
    )
    assert parsed["correlation_id"] == "cid-1"
    assert datetime.fromisoformat(str(parsed["time"])).utcoffset() is not None


def returns_null_correlation_id_when_logged_outside_a_request() -> None:
    record = logging.LogRecord("drlibre.demo", logging.INFO, __file__, 1, "hello", None, None)

    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["correlation_id"] is None


def returns_request_line_with_method_route_pattern_status_and_duration_when_request_ends(
    log_lines: list[dict[str, object]],
) -> None:
    browser_api_client().get("/api/v1/health", headers={"x-correlation-id": "cid-3"})

    request_lines = [line for line in log_lines if line.get("logger") == "drlibre.request"]
    assert len(request_lines) == 1
    line = request_lines[0]
    assert (line["method"], line["route"], line["status"]) == ("GET", "api/v1/health", 200)
    assert isinstance(line["duration_ms"], int | float)
    assert line["correlation_id"] == "cid-3"


def returns_route_pattern_without_path_or_query_when_request_has_identifier_and_token(
    log_lines: list[dict[str, object]], settings: object
) -> None:
    settings.ROOT_URLCONF = "scheduling.views.probe_urls"  # type: ignore[attr-defined]

    browser_api_client().get(f"/api/v1/probe/patients/{EMAIL}?token={TOKEN}&email={EMAIL}")
    browser_api_client().get(f"/api/v1/missing/{EMAIL}?token={TOKEN}")

    request_lines = [line for line in log_lines if line.get("logger") == "drlibre.request"]
    assert [line["route"] for line in request_lines][0] == "api/v1/probe/patients/<str:email>"
    output = _raw_output(log_lines)
    assert EMAIL not in output
    assert TOKEN not in output


def returns_no_email_token_or_clinical_note_when_logged_through_args_extra_and_exception_message(
    log_lines: list[dict[str, object]],
) -> None:
    logger = logging.getLogger("drlibre.demo")

    logger.info("user %s", EMAIL, extra={"token": TOKEN})
    logger.warning("note %s %s", NOTE, TOKEN)
    try:
        raise ValueError(f"{EMAIL} {NOTE} {TOKEN}")
    except ValueError:
        logger.exception("failed")

    output = _raw_output(log_lines)
    for secret in (EMAIL, TOKEN, NOTE):
        assert secret not in output
    failed = [line for line in log_lines if line["message"] == "failed"][0]
    assert "ValueError" in json.dumps(failed)
    assert "test_json_logging.py" in json.dumps(failed)


def returns_no_sensitive_text_and_trace_frames_when_view_raises_unexpected_error(
    log_lines: list[dict[str, object]], probe_client: Client
) -> None:
    probe_client.get("/api/v1/probe/explode")

    output = _raw_output(log_lines)
    for secret in (EMAIL, TOKEN, NOTE):
        assert secret not in output
    assert "ValueError" in output
    assert "probe_views.py" in output


def returns_correlation_id_on_every_line_when_request_logs_several_lines(
    log_lines: list[dict[str, object]], probe_client: Client
) -> None:
    probe_client.get("/api/v1/probe/explode", headers={"x-correlation-id": "cid-all"})

    assert len(log_lines) >= 2
    assert {line["correlation_id"] for line in log_lines} == {"cid-all"}


def returns_no_extra_field_outside_the_request_keys_when_record_carries_one(
    log_lines: list[dict[str, object]],
) -> None:
    logging.getLogger("drlibre.demo").info("hello", extra={"path": f"/x/{EMAIL}", "status": 7})

    assert set(log_lines[0]) == {"time", "level", "logger", "message", "correlation_id", "status"}


def returns_404_status_and_duration_in_milliseconds_when_unknown_path_is_requested(
    log_lines: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    readings = iter([10.0, 10.25])
    monkeypatch.setattr(time, "perf_counter", lambda: next(readings))

    browser_api_client().get("/api/v1/nothing-here")

    line = [item for item in log_lines if item.get("logger") == "drlibre.request"][0]
    assert (line["status"], line["duration_ms"]) == (404, 250.0)
