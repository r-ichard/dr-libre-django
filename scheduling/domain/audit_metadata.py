"""Section 4: audit metadata holds only ids, counts, status values, names of changed fields and
an email domain. Each section has a type that cannot carry free text, so names, emails, phone
numbers, birth dates, reasons and clinical notes have no place."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import NewType
from uuid import UUID

KEY_PATTERN = re.compile(r"[a-z][a-z_]{2,40}")
FIELD_NAME_PATTERN = re.compile(r"[a-z][a-z_]{1,60}")
HOSTNAME_PATTERN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")
ID_SUFFIXES = ("_id", "_ids")
COUNT_SUFFIX = "_count"
STATUS_SUFFIX = "_status"

FieldName = NewType("FieldName", str)
EmailDomain = NewType("EmailDomain", str)


def field_name(name: str) -> FieldName:
    if FIELD_NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("a field name is lower case letters and underscores only")
    return FieldName(name)


def email_domain(address: str) -> EmailDomain:
    """Keeps the part after the last at sign; the local part never leaves this function."""
    _, separator, domain = address.rpartition("@")
    if not separator or HOSTNAME_PATTERN.fullmatch(domain.lower()) is None:
        raise ValueError("an email domain is a host name taken from an address")
    return EmailDomain(domain.lower())


def _check_key(key: str, suffixes: tuple[str, ...]) -> None:
    if KEY_PATTERN.fullmatch(key) is None or not key.endswith(suffixes):
        raise ValueError(f"key must name its kind and end with one of {suffixes}")


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class AuditMetadata:
    ids: Mapping[str, UUID | int] = field(default_factory=dict)
    counts: Mapping[str, int] = field(default_factory=dict)
    statuses: Mapping[str, StrEnum] = field(default_factory=dict)
    changed_fields: tuple[FieldName, ...] = ()
    email_domain: EmailDomain | None = None

    def __post_init__(self) -> None:
        for name in self.changed_fields:
            field_name(name)
        if self.email_domain is not None and HOSTNAME_PATTERN.fullmatch(self.email_domain) is None:
            raise ValueError("an email domain is a host name taken from an address")
        for key, identifier in self.ids.items():
            _check_key(key, ID_SUFFIXES)
            if not isinstance(identifier, UUID) and not _is_plain_int(identifier):
                raise ValueError("an id is a UUID or an integer")
        for key, count in self.counts.items():
            _check_key(key, (COUNT_SUFFIX,))
            if not _is_plain_int(count):
                raise ValueError("a count is an integer")
        for key, status in self.statuses.items():
            _check_key(key, (STATUS_SUFFIX,))
            if not isinstance(status, StrEnum):
                raise ValueError("a status is a member of a StrEnum")

    def to_json(self) -> dict[str, object]:
        return {
            "ids": {key: str(identifier) for key, identifier in self.ids.items()},
            "counts": dict(self.counts),
            "statuses": {key: status.value for key, status in self.statuses.items()},
            "changed_fields": list(self.changed_fields),
            "email_domain": self.email_domain,
        }
