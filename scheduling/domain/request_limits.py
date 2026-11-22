"""Task 17a/17b: the sizes and ranges a request may have. Pure, so mutation testing covers them."""

from datetime import UTC, date, datetime

MAXIMUM_BODY_BYTES = 1024 * 1024
MAXIMUM_FIELDS = 200
MAXIMUM_JSON_DEPTH = 20
MAXIMUM_PAGE = 1_000_000
EARLIEST_INSTANT = datetime(2000, 1, 1, tzinfo=UTC)
LATEST_INSTANT = datetime(2100, 1, 1, tzinfo=UTC)
JSON_OPENERS = b"[{"
JSON_CLOSERS = b"]}"
QUOTE = ord('"')
BACKSLASH = ord("\\")


def json_depth(raw: bytes) -> int:
    """Deepest bracket nesting outside strings; a scan, so a hostile body cannot recurse."""
    depth = deepest = 0
    in_string = escaped = False
    for byte in raw:
        if in_string:
            in_string = not (byte == QUOTE and not escaped)
            escaped = byte == BACKSLASH and not escaped
        elif byte == QUOTE:
            in_string = True
        elif byte in JSON_OPENERS:
            depth += 1
            deepest = max(deepest, depth)
        elif byte in JSON_CLOSERS:
            depth -= 1
    return deepest


def declared_length(header: str) -> int | None:
    """The Content-Length as a number; None when the header is not a non-negative integer."""
    if not header:
        return 0
    text = header.strip()
    return int(text) if text.isascii() and text.isdigit() else None


def query_field_count(query_string: str) -> int:
    return query_string.count("&") + 1 if query_string else 0


def instant_in_range(instant: datetime) -> bool:
    return EARLIEST_INSTANT <= instant < LATEST_INSTANT


def day_in_range(day: date) -> bool:
    """A calendar day a page may be asked for; the arithmetic around it cannot overflow."""
    return EARLIEST_INSTANT.date() <= day < LATEST_INSTANT.date()
