from collections.abc import Mapping

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from scheduling.domain.failure import Failure, FieldMessage, Result, Success
from scheduling.domain.text_rules import check_storable_text

NON_FIELD_NAME = "non_field_errors"

type ErrorTree = dict[str, ErrorTree] | list[str]


class StrictTextRules(serializers.CharField):
    """Task 27a: DRF turns a number into text; a text field of the API refuses it, and applies the
    one text rule of the domain. Mixed into every text field type a request schema uses."""

    single_line = False

    def to_internal_value(self, data: object) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        checked = check_storable_text(self.field_name or "", data, single_line=self.single_line)
        if isinstance(checked, Failure):
            raise ValidationError(checked.field_messages[0].message)
        return super().to_internal_value(data)


class StrictText(StrictTextRules):
    pass


class StrictLine(StrictTextRules):
    single_line = True


class StrictEmail(StrictTextRules, serializers.EmailField):
    single_line = True


class StrictCode(StrictTextRules, serializers.RegexField):
    single_line = True


class StrictSerializer(serializers.Serializer[Mapping[str, object]]):
    """Request schema base: a key that is not a writable field is refused at every depth."""

    def to_internal_value(self, data: Mapping[str, object]) -> dict[str, object]:
        unknown = unknown_fields(self, data)
        if unknown:
            raise ValidationError(unknown)
        return dict(super().to_internal_value(data))


def unknown_fields(schema: object, data: object) -> dict[str, ErrorTree]:
    """Error tree, shaped like DRF's own, naming every key no writable field accepts."""
    if isinstance(schema, serializers.ListSerializer):
        if not isinstance(data, list):
            return {}
        items = {str(index): unknown_fields(schema.child, item) for index, item in enumerate(data)}
        return {index: errors for index, errors in items.items() if errors}
    if not isinstance(schema, serializers.Serializer) or not isinstance(data, Mapping):
        return {}
    errors: dict[str, ErrorTree] = {}
    for key in sorted(str(key) for key in data):
        field = schema.fields.get(key)
        if field is None or field.read_only:
            errors[key] = ["Unknown field."]
        else:
            nested = unknown_fields(field, data[key])
            if nested:
                errors[key] = nested
    return errors


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
