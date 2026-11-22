"""Task 22, spec 15.1 and 4: every failure under /fhir as an OperationOutcome. The text is fixed
and the only variable part is the correlation id, so no input or internals can leak."""

from scheduling.domain.failure import Failure
from scheduling.domain.fhir_common import Resource, extension
from scheduling.domain.fhir_write_failures import outcome_for

FAILURE_CODE_EXTENSION = "failure-code"


def operation_outcome(
    issue_code: str,
    text: str,
    correlation_id: str,
    expressions: tuple[str, ...] = (),
    product_code: str = "",
) -> Resource:
    issue: Resource = {
        "severity": "error",
        "code": issue_code,
        "details": {"text": text},
        "diagnostics": correlation_id,
    }
    if expressions:
        issue["expression"] = list(expressions)
    if product_code:
        issue["extension"] = [extension(FAILURE_CODE_EXTENSION, "valueCode", product_code)]
    return {"resourceType": "OperationOutcome", "issue": [issue]}


def failure_outcome(failure: Failure, text: str, correlation_id: str) -> Resource:
    answer = outcome_for(failure)
    return operation_outcome(
        answer.issue_code, text, correlation_id, _refused_names(failure), answer.product_code
    )


def _refused_names(failure: Failure) -> tuple[str, ...]:
    raw = failure.details.get("fields", [])
    if not isinstance(raw, list):
        return ()
    return tuple(item["field"] for item in raw if isinstance(item, dict) and "field" in item)


def information_outcome(text: str, correlation_id: str) -> Resource:
    """The answer to a delete: FHIR JSON like every other answer, saying what happened."""
    issue: Resource = {
        "severity": "information",
        "code": "informational",
        "details": {"text": text},
        "diagnostics": correlation_id,
    }
    return {"resourceType": "OperationOutcome", "issue": [issue]}
