"""Removes what FHIR forbids (empty arrays, objects and strings, nulls). Every response passes
through this one function, so no mapper has to remember the rule."""


def without_empty(value: object) -> object:
    """A copy of `value` with every None, empty string, empty list and empty object removed,
    children first, so a container that only held empties goes too. False and 0 stay."""
    if isinstance(value, dict):
        cleaned_fields = {name: without_empty(item) for name, item in value.items()}
        return {name: item for name, item in cleaned_fields.items() if not _is_empty(item)}
    if isinstance(value, list):
        cleaned_items = [without_empty(item) for item in value]
        return [item for item in cleaned_items if not _is_empty(item)]
    return value


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str | list | dict) and len(value) == 0)
