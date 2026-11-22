"""Task 23, spec 15.1 and 4: the product code of a failure rides in the OperationOutcome so a
client can act on it."""

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.fhir_common import extension_url
from scheduling.domain.fhir_outcome import failure_outcome, operation_outcome
from scheduling.domain.fhir_write_failures import stale_version

EXPECTED_EXTENSION = [{"url": extension_url("failure-code"), "valueCode": "has_dependents"}]


def returns_extension_with_the_product_code_when_one_is_given() -> None:
    outcome = operation_outcome("conflict", "t", "c", (), "has_dependents")

    assert outcome["issue"][0]["extension"] == EXPECTED_EXTENSION  # type: ignore[index]


def returns_no_extension_when_no_product_code_is_given() -> None:
    assert "extension" not in operation_outcome("conflict", "t", "c")["issue"][0]  # type: ignore[index]


def returns_the_product_code_of_the_failure_when_a_failure_is_an_outcome() -> None:
    outcome = failure_outcome(Failure(FailureCode.HAS_DEPENDENTS), "t", "c")

    assert outcome["issue"][0]["extension"] == EXPECTED_EXTENSION  # type: ignore[index]


def returns_one_rule_extension_per_violated_rule_when_a_rule_is_violated() -> None:
    failure = Failure.rule_violation(["lead_time_too_short", "outside_availability"])

    issue = failure_outcome(failure, "t", "c")["issue"][0]  # type: ignore[index]

    assert issue["extension"][1:] == [
        {"url": extension_url("violated-rule"), "valueCode": "lead_time_too_short"},
        {"url": extension_url("violated-rule"), "valueCode": "outside_availability"},
    ]


def returns_one_conflict_extension_per_resource_when_a_slot_is_in_conflict() -> None:
    issue = failure_outcome(Failure.conflict(["clinician"]), "t", "c")["issue"][0]  # type: ignore[index]

    assert issue["extension"][1:] == [
        {"url": extension_url("conflicting-resource"), "valueCode": "clinician"}
    ]


def returns_no_conflict_extension_when_the_conflict_is_a_stale_version() -> None:
    issue = failure_outcome(stale_version(), "t", "c")["issue"][0]  # type: ignore[index]

    assert len(issue["extension"]) == 1
