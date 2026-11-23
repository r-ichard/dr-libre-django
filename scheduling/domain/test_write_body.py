"""Section 14: the one rule for "does a write carry a body, and does it say JSON"."""

import pytest

from scheduling.domain.write_body import carries_body, unsupported_media_type

JSON_TYPES = ("application/json",)


@pytest.mark.parametrize(
    ("content_length", "transfer_encoding", "expected"),
    [
        (None, None, False),
        ("", None, False),
        ("0", None, False),
        (" 0 ", None, False),
        ("12", None, True),
        (None, "chunked", True),
        ("", "chunked", True),
    ],
)
def returns_whether_the_write_carries_a_body(
    content_length: str | None, transfer_encoding: str | None, expected: bool
) -> None:
    assert carries_body(content_length, transfer_encoding) is expected


def returns_the_media_type_when_a_body_names_another_type() -> None:
    assert (
        unsupported_media_type("5", None, "text/plain; charset=utf-8", JSON_TYPES) == "text/plain"
    )


def returns_none_when_a_body_says_json_in_any_case_with_parameters() -> None:
    assert (
        unsupported_media_type("5", None, " Application/JSON ; charset=utf-8", JSON_TYPES) is None
    )


def returns_none_when_there_is_no_body_whatever_the_type() -> None:
    assert unsupported_media_type(None, None, "text/plain", JSON_TYPES) is None


def returns_the_media_type_for_a_chunked_body_of_another_type() -> None:
    assert unsupported_media_type(None, "chunked", "text/plain", JSON_TYPES) == "text/plain"
