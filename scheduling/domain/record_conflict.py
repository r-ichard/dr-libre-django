"""Section 10: which fields a stale admin save lists, with the value read, stored and typed."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadKnown:
    text: str


@dataclass(frozen=True)
class ReadUnknown:
    pass


ReadValue = ReadKnown | ReadUnknown


@dataclass(frozen=True)
class FieldConflict:
    field: str
    label: str
    read: ReadValue
    stored: str
    typed: str


def conflicting_fields(
    labels: Mapping[str, str],
    read: Mapping[str, ReadValue],
    stored: Mapping[str, str],
    typed: Mapping[str, str],
) -> list[FieldConflict]:
    rows: list[FieldConflict] = []
    for field, label in labels.items():
        read_value = read.get(field, ReadUnknown())
        stored_text = stored[field]
        typed_text = typed[field]
        read_changed = isinstance(read_value, ReadKnown) and read_value.text != stored_text
        if read_changed or typed_text != stored_text:
            rows.append(FieldConflict(field, label, read_value, stored_text, typed_text))
    return rows
