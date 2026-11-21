import pytest

from scripts.mutation_survivors import check_survivors, parse_equivalents

RESULTS = "\n".join(
    [
        "    scheduling.domain.free_slots.x_free_slots__mutmut_3: survived",
        "    scheduling.domain.free_slots.x_free_slots__mutmut_4: killed",
        "    scheduling.domain.audit_metadata.x_clean__mutmut_9: survived",
        "    scheduling.domain.audit_metadata.x_clean__mutmut_10: no tests",
    ]
)
EQUIVALENTS = "\n".join(
    [
        "# comment lines are ignored",
        "scheduling.domain.free_slots.x_free_slots__mutmut_3: only reorders two independent checks",
        "",
    ]
)


def returns_unlisted_survivors_when_results_hold_survivors_without_a_reason() -> None:
    report = check_survivors(RESULTS, parse_equivalents(EQUIVALENTS))
    assert report.unlisted == ["scheduling.domain.audit_metadata.x_clean__mutmut_9"]


def returns_no_unlisted_survivors_when_every_survivor_has_a_listed_reason() -> None:
    equivalents = parse_equivalents(
        EQUIVALENTS + "scheduling.domain.audit_metadata.x_clean__mutmut_9: unobservable length\n"
    )
    assert check_survivors(RESULTS, equivalents).unlisted == []


def returns_stale_entries_when_a_listed_mutant_no_longer_survives() -> None:
    equivalents = parse_equivalents("scheduling.domain.free_slots.x_gone__mutmut_1: was equal\n")
    assert check_survivors(RESULTS, equivalents).stale == [
        "scheduling.domain.free_slots.x_gone__mutmut_1"
    ]


def raises_system_exit_when_an_equivalent_entry_has_no_reason() -> None:
    with pytest.raises(SystemExit) as error:
        parse_equivalents("scheduling.domain.free_slots.x_free_slots__mutmut_3:   \n")
    assert str(error.value) == (
        "mutation-equivalents.txt: no reason for "
        "scheduling.domain.free_slots.x_free_slots__mutmut_3"
    )
