"""Fail when saved `mutmut results` list a survivor that mutation-equivalents.txt lacks."""

import sys
from dataclasses import dataclass
from pathlib import Path

EQUIVALENTS_FILE = Path(__file__).parent.parent / "mutation-equivalents.txt"
SURVIVED_SUFFIX = ": survived"


@dataclass(frozen=True)
class SurvivorReport:
    unlisted: list[str]
    stale: list[str]


def main() -> int:
    results = Path(sys.argv[1]).read_text()
    equivalents = parse_equivalents(
        EQUIVALENTS_FILE.read_text() if EQUIVALENTS_FILE.exists() else ""
    )
    report = check_survivors(results, equivalents)
    for name in report.stale:
        print(f"stale entry in {EQUIVALENTS_FILE.name}: {name}")
    for name in report.unlisted:
        print(f"unlisted survivor: {name}")
    return 1 if report.unlisted or report.stale else 0


def parse_equivalents(text: str) -> dict[str, str]:
    equivalents: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, _, reason = line.partition(":")
        if not reason.strip():
            raise SystemExit(f"{EQUIVALENTS_FILE.name}: no reason for {name.strip()}")
        equivalents[name.strip()] = reason.strip()
    return equivalents


def check_survivors(results_text: str, equivalents: dict[str, str]) -> SurvivorReport:
    survivors = [
        line.strip().removesuffix(SURVIVED_SUFFIX)
        for line in results_text.splitlines()
        if line.strip().endswith(SURVIVED_SUFFIX)
    ]
    return SurvivorReport(
        unlisted=[name for name in survivors if name not in equivalents],
        stale=[name for name in equivalents if name not in survivors],
    )


if __name__ == "__main__":
    sys.exit(main())
