import json
import logging
import traceback
from datetime import UTC, datetime

from scheduling.use_cases.request_context import current_request_context

REQUEST_KEYS = ("method", "route", "status", "duration_ms", "job", "counts")


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Sensitive data stays out by construction: only an allowlist
    of record fields is read, args are never interpolated, exception messages are dropped."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            correlation_id: str | None = current_request_context().correlation_id
        except LookupError:
            correlation_id = None
        line: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": str(record.msg),
            "correlation_id": correlation_id,
        }
        for key in REQUEST_KEYS:
            if hasattr(record, key):
                line[key] = getattr(record, key)
        if record.exc_info is not None and record.exc_info[0] is not None:
            exception_type, _, trace = record.exc_info
            line["exception"] = {
                "type": exception_type.__name__,
                "frames": [
                    f"{frame.filename}:{frame.lineno} {frame.name}: {frame.line}"
                    for frame in traceback.extract_tb(trace)
                ],
            }
        return json.dumps(line)
