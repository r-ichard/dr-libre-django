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
