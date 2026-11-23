"""Section 17: every open point of ADR 0005 to 0007 is closed or is a question for the
owner, collected at the end of ADR 0007; the README shows the FHIR API with commands that run."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_HEADING = "## Questions for the owner"
FIRST_THREE = ("0005-fhir-conventions", "0006-fhir-schedule-slot-patient-writes")
LAST = "0007-fhir-appointment-and-the-rest"


def _adr(name: str) -> str:
    return (ROOT / "doc" / "adr" / f"{name}.md").read_text()


def _questions() -> list[str]:
    text = _adr(LAST)
    assert QUESTIONS_HEADING in text, "ADR 0007 has no list of questions for the owner"
    section = text.split(QUESTIONS_HEADING, 1)[1]
    return re.findall(r"^\d+\. .*(?:\n(?!\d+\. ).+)*", section, flags=re.MULTILINE)


def returns_the_questions_for_the_owner_at_the_end_of_adr_0007_each_with_todays_choice() -> None:
    questions = _questions()

    assert len(questions) >= 4
    assert all("Today the product:" in item for item in questions)
    assert _adr(LAST).rstrip().endswith(questions[-1].rstrip())


def returns_no_open_point_outside_the_list_when_adr_0005_to_0007_are_read() -> None:
    texts = [_adr(name) for name in (*FIRST_THREE, LAST)]

    open_point_blocks = [
        text.split("## Open points for the owner", 1)[1].split("\n## ", 1)[0]
        for text in texts
        if "## Open points for the owner" in text
    ]

    assert all(QUESTIONS_HEADING.removeprefix("## ") in block for block in open_point_blocks)
    assert all("\n- " not in block.replace("\n- See", "\n") for block in open_point_blocks)


def returns_the_fhir_api_section_with_token_read_search_booking_refusal_and_validate() -> None:
    path = ROOT / "README.md"
    assert path.exists(), "README.md does not exist"
    readme = path.read_text()
    assert "## FHIR API" in readme, "README.md has no FHIR API section"

    section = readme.split("## FHIR API", 1)[1]
    assert "api_tokens" in section
    assert section.count("curl ") >= 4
    assert "make fhir-validate" in section
    assert "<token>" in section
    assert "Bearer eyJ" not in section
