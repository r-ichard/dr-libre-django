"""One rule for "does this write carry a body, and does it say JSON", shared by `/api/v1` and
`/fhir`. A browser sends text/plain across sites without a preflight, so a body must name JSON."""

from collections.abc import Sequence


def carries_body(content_length: str | None, transfer_encoding: str | None) -> bool:
    """RFC 9112, section 6.3: a request without Content-Length and Transfer-Encoding has no body;
    an empty Content-Length is how the server reports that the client sent none."""
    if transfer_encoding is not None:
        return True
    return content_length is not None and content_length.strip() not in ("", "0")


def unsupported_media_type(
    content_length: str | None,
    transfer_encoding: str | None,
    content_type: str,
    accepted: Sequence[str],
) -> str | None:
    """The media type a body names when it is not one of `accepted`, else None."""
    if not carries_body(content_length, transfer_encoding):
        return None
    media_type = content_type.split(";")[0].strip().lower()
    return None if media_type in accepted else media_type
