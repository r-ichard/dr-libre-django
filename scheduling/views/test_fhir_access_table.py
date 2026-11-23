"""The access table of the /fhir declaration lists each declared resource type and interaction
once, and nothing else."""

from collections import Counter

from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from test_support.fhir_access_rows import FHIR_ACCESS_ROWS

PairKey = tuple[str, str]


def _declared_keys() -> set[PairKey]:
    return {
        (declaration.type, interaction)
        for declaration in FHIR_RESOURCES
        for interaction in declaration.interactions
    }


def _row_keys() -> list[PairKey]:
    return [(row.resource, row.interaction) for row in FHIR_ACCESS_ROWS]


def returns_no_interaction_unlisted_when_the_declaration_is_read() -> None:
    unlisted = sorted(_declared_keys() - set(_row_keys()))

    assert unlisted == []


def returns_no_row_for_a_removed_interaction_when_the_declaration_is_read() -> None:
    removed = sorted(set(_row_keys()) - _declared_keys())

    assert removed == []


def returns_one_row_per_interaction_when_the_table_is_read() -> None:
    repeated = sorted(key for key, count in Counter(_row_keys()).items() if count > 1)

    assert repeated == []
