"""Task 23, spec 15.5: Slot search needs a start range and a service type."""

from scheduling.domain.failure import Failure
from scheduling.domain.fhir_declaration import declaration_for
from scheduling.domain.fhir_search import parse_search

SLOT = declaration_for("Slot")
TYPE = "11111111-1111-1111-1111-111111111111"


def _parse(**params: list[str]) -> object:
    assert SLOT is not None
    return parse_search(SLOT, params)


def returns_failure_naming_start_when_start_is_missing() -> None:
    result = _parse(**{"service-type": [TYPE]})

    assert isinstance(result, Failure)
    assert result.details["fields"][0]["field"] == "start"  # type: ignore[index]


def returns_failure_naming_start_when_start_is_given_three_times() -> None:
    result = _parse(
        **{"service-type": [TYPE], "start": ["ge2030-01-01", "lt2030-01-02", "lt2030-01-03"]}
    )

    assert isinstance(result, Failure)
    assert result.details["fields"][0]["field"] == "start"  # type: ignore[index]


def returns_success_when_start_has_ge_and_lt() -> None:
    result = _parse(**{"service-type": [TYPE], "start": ["ge2030-01-01", "lt2030-01-02"]})

    assert not isinstance(result, Failure)


def returns_the_fixed_text_when_a_required_parameter_is_missing() -> None:
    result = _parse(**{"service-type": [TYPE]})

    assert isinstance(result, Failure)
    assert result.details["fields"][0]["message"] == "This search parameter is required."  # type: ignore[index]


def returns_the_once_only_text_when_a_paging_parameter_is_given_twice() -> None:
    result = _parse(**{"_count": ["1", "2"]})

    assert isinstance(result, Failure)
    assert result.details["fields"][0]["message"] == "A parameter may be given once."  # type: ignore[index]
