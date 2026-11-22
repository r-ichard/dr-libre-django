"""Task 17a: the sizes an API request may have, checked before any parser or schema sees it."""

from rest_framework.exceptions import ValidationError
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
