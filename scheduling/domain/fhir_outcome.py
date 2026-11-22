"""Task 22, spec 15.1 and 4: every failure under /fhir as an OperationOutcome. The text is fixed
and the only variable part is the correlation id, so no input or internals can leak."""

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.fhir_common import Resource

ISSUE_CODE_BY_FAILURE: dict[FailureCode, str] = {
    FailureCode.INVALID_INPUT: "invalid",
    FailureCode.UNAUTHENTICATED: "login",
    FailureCode.FORBIDDEN: "forbidden",
    FailureCode.NOT_FOUND: "not-found",
    FailureCode.RATE_LIMITED: "throttled",
}
FALLBACK_ISSUE_CODE = "processing"


def operation_outcome(
    issue_code: str, text: str, correlation_id: str, expressions: tuple[str, ...] = ()
) -> Resource:
    issue: Resource = {
        "severity": "error",
        "code": issue_code,
        "details": {"text": text},
        "diagnostics": correlation_id,
    }
    if expressions:
        issue["expression"] = list(expressions)
    return {"resourceType": "OperationOutcome", "issue": [issue]}


def failure_outcome(failure: Failure, text: str, correlation_id: str) -> Resource:
    code = ISSUE_CODE_BY_FAILURE.get(failure.code, FALLBACK_ISSUE_CODE)
    return operation_outcome(code, text, correlation_id, _refused_names(failure))


def _refused_names(failure: Failure) -> tuple[str, ...]:
    raw = failure.details.get("fields", [])
    if not isinstance(raw, list):
        return ()
    return tuple(item["field"] for item in raw if isinstance(item, dict) and "field" in item)
