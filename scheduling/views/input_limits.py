"""Task 17a: the sizes an API request may have, checked before any parser or schema sees it."""

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

MAXIMUM_BODY_BYTES = 1024 * 1024
MAXIMUM_FIELDS = 200
MAXIMUM_JSON_DEPTH = 20
JSON_OPENERS = b"[{"
JSON_CLOSERS = b"]}"
QUOTE = ord('"')
BACKSLASH = ord("\\")


def refuse_oversized(request: Request) -> None:
    """Raises the contract's invalid_input naming the part that is too large or too deep."""
    if request.META.get("QUERY_STRING", "").count("&") >= MAXIMUM_FIELDS:
        raise ValidationError({"query": ["Too many fields."]})
    length = int(request.META.get("CONTENT_LENGTH") or 0)
    if length > MAXIMUM_BODY_BYTES:
        raise ValidationError({"body": ["The request body is too large."]})
    if "json" in request.content_type and json_depth(request.body) > MAXIMUM_JSON_DEPTH:
        raise ValidationError({"body": ["The request body is nested too deeply."]})


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
