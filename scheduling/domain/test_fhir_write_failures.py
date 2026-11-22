"""Task 23, spec 4 and 15.1: one table gives every failure code its HTTP status and issue code."""

import pytest

from scheduling.domain.failure import Failure, FailureCode
from scheduling.domain.fhir_write_failures import STALE_VERSION, outcome_for, outcome_of

EXPECTED = {
    FailureCode.INVALID_INPUT: (400, "invalid"),
    FailureCode.UNAUTHENTICATED: (401, "login"),
    FailureCode.FORBIDDEN: (403, "forbidden"),
    FailureCode.NOT_FOUND: (404, "not-found"),
    FailureCode.CONFLICT: (409, "conflict"),
    FailureCode.HAS_DEPENDENTS: (409, "conflict"),
    FailureCode.RULE_VIOLATION: (422, "business-rule"),
}


@pytest.mark.parametrize(("code", "expected"), EXPECTED.items())
def returns_status_and_issue_code_of_section_4(
    code: FailureCode, expected: tuple[int, str]
) -> None:
    answer = outcome_of(code)

    assert (answer.status, answer.issue_code) == expected


def returns_a_status_for_every_failure_code() -> None:
    assert all(outcome_of(code).status >= 400 for code in FailureCode)


def returns_412_for_a_stale_version() -> None:
    assert (STALE_VERSION.status, STALE_VERSION.issue_code) == (412, "conflict")


def returns_the_product_code_so_a_client_can_tell_the_two_conflicts_apart() -> None:
    assert outcome_of(FailureCode.HAS_DEPENDENTS).product_code == "has_dependents"
    assert outcome_of(FailureCode.CONFLICT).product_code == "conflict"


def returns_412_only_for_a_conflict_that_names_version() -> None:
    stale = Failure(FailureCode.CONFLICT, {"resources": ["version"]})
    other = Failure(FailureCode.CONFLICT, {"resources": ["room"]})
    not_a_conflict = Failure(FailureCode.FORBIDDEN, {"resources": ["version"]})

    assert outcome_for(stale) == STALE_VERSION
    assert outcome_for(other).status == 409
    assert outcome_for(not_a_conflict).status == 403
    assert outcome_for(Failure(FailureCode.CONFLICT)).status == 409
