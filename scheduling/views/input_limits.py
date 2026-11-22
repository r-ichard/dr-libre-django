"""Task 17a: the sizes an API request may have, checked before any parser or schema sees it."""

from rest_framework.exceptions import UnsupportedMediaType, ValidationError
from rest_framework.request import Request

from scheduling.domain.request_limits import (
    MAXIMUM_BODY_BYTES,
    MAXIMUM_FIELDS,
    MAXIMUM_JSON_DEPTH,
    declared_length,
    json_depth,
    query_field_count,
)


def refuse_oversized(request: Request) -> None:
    """Raises the contract's invalid_input naming the part that is too large or too deep."""
    if query_field_count(request.META.get("QUERY_STRING", "")) > MAXIMUM_FIELDS:
        raise ValidationError({"query": ["Too many fields."]})
    length = declared_length(request.META.get("CONTENT_LENGTH", ""))
    if length is None:
        raise ValidationError({"body": ["The Content-Length header is not a number."]})
    if length > MAXIMUM_BODY_BYTES:
        raise ValidationError({"body": ["The request body is too large."]})
    if "json" in request.content_type and json_depth(request.body) > MAXIMUM_JSON_DEPTH:
        raise ValidationError({"body": ["The request body is nested too deeply."]})


def refuse_non_json_write(request: Request) -> None:
    """A browser sends text/plain and form bodies across sites without a preflight, so a write that
    carries a body must say it is JSON. A write without a body carries nothing to forge, and
    wsgiref names its type text/plain when the client sent no header."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    # The server drops CONTENT_LENGTH when the client sent none; an empty one is a malformed body.
    declared = request.META.get("CONTENT_LENGTH")
    has_body = (declared is not None and declared != "0") or (
        "HTTP_TRANSFER_ENCODING" in request.META
    )
    media_type = request.content_type.split(";")[0].strip().lower()
    if has_body and media_type != "application/json":
        raise UnsupportedMediaType(media_type)
