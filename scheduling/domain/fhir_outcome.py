"""Task 22, spec 15.1 and 4: every failure under /fhir as an OperationOutcome. The text is fixed
and the only variable part is the correlation id, so no input or internals can leak."""

from scheduling.domain.failure import Failure
from scheduling.domain.fhir_common import Resource, extension
from scheduling.domain.fhir_write_failures import STALE_VERSION, outcome_for

FAILURE_CODE_EXTENSION = "failure-code"


def operation_outcome(
    issue_code: str,
    text: str,
    correlation_id: str,
    expressions: tuple[str, ...] = (),
    product_code: str = "",
    details: list[Resource] | None = None,
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
        issue["extension"] = [
            extension(FAILURE_CODE_EXTENSION, "valueCode", product_code),
            *(details or []),
        ]
    return {"resourceType": "OperationOutcome", "issue": [issue]}


def failure_outcome(failure: Failure, text: str, correlation_id: str) -> Resource:
    answer = outcome_for(failure)
    details = [] if answer is STALE_VERSION else _detail_extensions(failure)
    return operation_outcome(
        answer.issue_code,
        text,
        _with_messages(failure, _with_dependents(failure, correlation_id)),
        _refused_names(failure),
        answer.product_code,
        details,
    )


def _with_dependents(failure: Failure, correlation_id: str) -> str:
    """What still uses the record, as the console's delete page says it: counts and fixed words."""
    names = failure.details.get("dependents")
    if not isinstance(names, list):
        return correlation_id
    return f"{correlation_id} Still used by: {', '.join(str(name) for name in names)}."


def _with_messages(failure: Failure, diagnostics: str) -> str:
    """What to fix, as `/api/v1` says it: the fixed message of each refused field."""
    raw = failure.details.get("fields", [])
    said = [
        f"{item['field']}: {item['message']}"
        for item in (raw if isinstance(raw, list) else [])
        if isinstance(item, dict) and "message" in item and "field" in item
    ]
    return f"{diagnostics} {' '.join(said)}" if said else diagnostics


def _detail_extensions(failure: Failure) -> list[Resource]:
    """Rule names and conflicting resources are fixed vocabulary, never client input."""
    found: list[Resource] = []
    for key, name in (("violated_rules", "violated-rule"), ("resources", "conflicting-resource")):
        names = failure.details.get(key)
        if isinstance(names, list):
            found.extend(extension(name, "valueCode", item) for item in names)
    return found


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
