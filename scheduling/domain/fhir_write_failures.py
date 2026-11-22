"""Task 23, spec 4 and 15.1: the one table that gives every failure its HTTP status and the
OperationOutcome issue code, for reads and writes alike. The product code travels with it so a
client can tell two conflicts apart."""

from dataclasses import dataclass

from scheduling.domain.failure import Failure, FailureCode

STALE_RESOURCES = ["version"]


@dataclass(frozen=True)
class WriteOutcome:
    status: int
    issue_code: str
    product_code: str


STALE_VERSION = WriteOutcome(412, "conflict", "stale_version")

_TABLE: dict[FailureCode, tuple[int, str]] = {
    FailureCode.INVALID_INPUT: (400, "invalid"),
    FailureCode.UNAUTHENTICATED: (401, "login"),
    FailureCode.FORBIDDEN: (403, "forbidden"),
    FailureCode.NOT_FOUND: (404, "not-found"),
    FailureCode.CONFLICT: (409, "conflict"),
    FailureCode.NO_ROOM_AVAILABLE: (409, "conflict"),
    FailureCode.NO_CLINICIAN_AVAILABLE: (409, "conflict"),
    FailureCode.INVALID_TRANSITION: (409, "conflict"),
    FailureCode.HAS_DEPENDENTS: (409, "conflict"),
    FailureCode.RULE_VIOLATION: (422, "business-rule"),
    FailureCode.RATE_LIMITED: (429, "throttled"),
    FailureCode.MAIL_UNAVAILABLE: (503, "transient"),
}


def outcome_of(code: FailureCode) -> WriteOutcome:
    status, issue_code = _TABLE[code]
    return WriteOutcome(status, issue_code, code.value)


def outcome_for(failure: Failure) -> WriteOutcome:
    """A conflict that names `version` is a stale `If-Match`: 412, not 409."""
    if failure.code is FailureCode.CONFLICT and failure.details.get("resources") == STALE_RESOURCES:
        return STALE_VERSION
    return outcome_of(failure.code)


def stale_version() -> Failure:
    return Failure.conflict(STALE_RESOURCES)
