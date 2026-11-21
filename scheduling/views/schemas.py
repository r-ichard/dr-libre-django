from collections.abc import Mapping

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from scheduling.domain.failure import Failure, FieldMessage, Result, Success

NON_FIELD_NAME = "non_field_errors"


class StrictSerializer(serializers.Serializer[Mapping[str, object]]):
    """Request schema base: a key that is not a writable field is refused, never dropped."""

    def to_internal_value(self, data: Mapping[str, object]) -> dict[str, object]:
        if isinstance(data, Mapping):
            writable = {name for name, item in self.fields.items() if not item.read_only}
            unknown = sorted(str(key) for key in data if key not in writable)
            if unknown:
                raise ValidationError({name: ["Unknown field."] for name in unknown})
        return dict(super().to_internal_value(data))


def validate_body(
    schema_class: type[StrictSerializer], data: object
) -> Result[Mapping[str, object]]:
    schema = schema_class(data=data)
    if schema.is_valid():
        return Success(dict(schema.validated_data))
    return Failure.invalid_input(field_messages(schema.errors))


def field_messages(detail: object, prefix: str = "") -> list[FieldMessage]:
    if isinstance(detail, Mapping):
        messages: list[FieldMessage] = []
        for key, value in detail.items():
            messages += field_messages(value, f"{prefix}.{key}" if prefix else str(key))
        return messages
    if isinstance(detail, list | tuple):
        messages = []
        for item in detail:
            messages += field_messages(item, prefix)
        return messages
    return [FieldMessage(prefix or NON_FIELD_NAME, str(detail))]
