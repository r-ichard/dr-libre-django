from collections.abc import Mapping

from django.test import Client

from scheduling.domain.failure import FieldMessage
from scheduling.views.schemas import field_messages


def returns_dotted_field_name_when_error_is_nested() -> None:
    detail = {"address": {"city": ["Required."]}, "tags": ["Bad."]}

    assert field_messages(detail) == [
        FieldMessage("address.city", "Required."),
        FieldMessage("tags", "Bad."),
    ]


def returns_non_field_errors_name_when_error_has_no_field() -> None:
    assert field_messages(["Something is off."]) == [
        FieldMessage("non_field_errors", "Something is off.")
    ]


def _post_nested(client: Client, body: Mapping[str, object]) -> tuple[int, list[object]]:
    response = client.post("/api/v1/probe/nested-write", body, content_type="application/json")
    if response.status_code == 201:
        return 201, []
    return response.status_code, response.json()["error"]["details"]["fields"]


def returns_201_when_nested_body_has_only_known_fields(probe_client: Client) -> None:
    body = {"address": {"city": "Oslo"}, "items": [{"name": "a"}]}

    assert _post_nested(probe_client, body) == (201, [])


def returns_400_naming_nested_field_when_nested_object_has_unknown_key(
    probe_client: Client,
) -> None:
    body = {"address": {"city": "Oslo", "zip": "0150"}, "items": [{"name": "a"}]}

    assert _post_nested(probe_client, body) == (
        400,
        [{"field": "address.zip", "message": "Unknown field."}],
    )


def returns_400_naming_indexed_field_when_list_item_has_unknown_key(
    probe_client: Client,
) -> None:
    body = {"address": {"city": "Oslo"}, "items": [{"name": "a"}, {"name": "b", "sku": "x"}]}

    assert _post_nested(probe_client, body) == (
        400,
        [{"field": "items.1.sku", "message": "Unknown field."}],
    )
