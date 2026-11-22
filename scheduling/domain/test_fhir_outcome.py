"""Task 23, spec 15.1 and 4: the product code of a failure rides in the OperationOutcome so a
client can act on it."""

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.fhir_common import extension_url
from scheduling.domain.fhir_outcome import failure_outcome, operation_outcome

EXPECTED_EXTENSION = [{"url": extension_url("failure-code"), "valueCode": "has_dependents"}]


def returns_extension_with_the_product_code_when_one_is_given() -> None:
    outcome = operation_outcome("conflict", "t", "c", (), "has_dependents")

    assert outcome["issue"][0]["extension"] == EXPECTED_EXTENSION  # type: ignore[index]


def returns_no_extension_when_no_product_code_is_given() -> None:
    assert "extension" not in operation_outcome("conflict", "t", "c")["issue"][0]  # type: ignore[index]


def returns_the_product_code_of_the_failure_when_a_failure_is_an_outcome() -> None:
    outcome = failure_outcome(Failure(FailureCode.HAS_DEPENDENTS), "t", "c")

    assert outcome["issue"][0]["extension"] == EXPECTED_EXTENSION  # type: ignore[index]
