from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class FailureCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    NO_ROOM_AVAILABLE = "no_room_available"
    NO_CLINICIAN_AVAILABLE = "no_clinician_available"
    INVALID_TRANSITION = "invalid_transition"
    HAS_DEPENDENTS = "has_dependents"
    RULE_VIOLATION = "rule_violation"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class FieldMessage:
    field: str
    message: str


@dataclass(frozen=True)
class Failure:
    """An expected failure. One constructor per code keeps details tied to their code."""

    code: FailureCode
    details: dict[str, object] = field(default_factory=dict)

    @classmethod
    def invalid_input(cls, fields: Sequence[FieldMessage]) -> Failure:
        return cls(FailureCode.INVALID_INPUT, {"fields": [asdict(item) for item in fields]})

    @classmethod
    def unauthenticated(cls) -> Failure:
        return cls(FailureCode.UNAUTHENTICATED)

    @classmethod
    def forbidden(cls) -> Failure:
        return cls(FailureCode.FORBIDDEN)

    @classmethod
    def not_found(cls) -> Failure:
        return cls(FailureCode.NOT_FOUND)

    @classmethod
    def conflict(cls, resources: Sequence[str]) -> Failure:
        return cls(FailureCode.CONFLICT, {"resources": list(resources)})

    @classmethod
    def no_room_available(cls) -> Failure:
        return cls(FailureCode.NO_ROOM_AVAILABLE)

    @classmethod
    def no_clinician_available(cls) -> Failure:
        return cls(FailureCode.NO_CLINICIAN_AVAILABLE)

    @classmethod
    def invalid_transition(cls, current_status: str) -> Failure:
        return cls(FailureCode.INVALID_TRANSITION, {"current_status": current_status})

    @classmethod
    def has_dependents(cls, dependents: Sequence[str]) -> Failure:
        return cls(FailureCode.HAS_DEPENDENTS, {"dependents": list(dependents)})

    @classmethod
    def rule_violation(cls, violated_rules: Sequence[str]) -> Failure:
        return cls(FailureCode.RULE_VIOLATION, {"violated_rules": list(violated_rules)})

    @classmethod
    def rate_limited(cls) -> Failure:
        return cls(FailureCode.RATE_LIMITED)


@dataclass(frozen=True)
class Success[Value]:
    value: Value


type Result[Value] = Success[Value] | Failure
