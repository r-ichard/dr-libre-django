import sys
from pathlib import Path

import pytest

from scripts import mutation_survivors
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


def returns_exit_one_when_a_listed_mutant_no_longer_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    results_file = tmp_path / "results.txt"
    results_file.write_text("    scheduling.domain.free_slots.x_free_slots__mutmut_3: survived\n")
    equivalents_file = tmp_path / "mutation-equivalents.txt"
    equivalents_file.write_text(
        "scheduling.domain.free_slots.x_free_slots__mutmut_3: "
        "only reorders two independent checks\n"
        "scheduling.domain.free_slots.x_gone__mutmut_1: was equal\n"
    )
    monkeypatch.setattr(mutation_survivors, "EQUIVALENTS_FILE", equivalents_file)
    monkeypatch.setattr(sys, "argv", ["mutation_survivors.py", str(results_file)])
    assert mutation_survivors.main() == 1
    printed = capsys.readouterr().out
    stale_name = "scheduling.domain.free_slots.x_gone__mutmut_1"
    assert f"stale entry in mutation-equivalents.txt: {stale_name}" in printed


def returns_exit_one_when_a_survivor_has_no_listed_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results_file = tmp_path / "results.txt"
    results_file.write_text("    scheduling.domain.free_slots.x_free_slots__mutmut_3: survived\n")
    equivalents_file = tmp_path / "mutation-equivalents.txt"
    equivalents_file.write_text("")
    monkeypatch.setattr(mutation_survivors, "EQUIVALENTS_FILE", equivalents_file)
    monkeypatch.setattr(sys, "argv", ["mutation_survivors.py", str(results_file)])
    assert mutation_survivors.main() == 1


def raises_system_exit_when_an_equivalent_entry_has_no_reason() -> None:
    with pytest.raises(SystemExit) as error:
        parse_equivalents("scheduling.domain.free_slots.x_free_slots__mutmut_3:   \n")
    assert str(error.value) == (
        "mutation-equivalents.txt: no reason for "
        "scheduling.domain.free_slots.x_free_slots__mutmut_3"
    )
