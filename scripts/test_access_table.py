"""The access section of doc/security-review.md: the renderer, the splice, and the drift check."""

from dataclasses import replace
from pathlib import Path

import pytest

from scheduling.views.pages.test_page_access_rows import OK, Answer, Caller, Row
from scheduling.views.test_api_access_rows import (
    AccessRow,
    KnownDifference,
    RecordUse,
)
from scheduling.views.test_api_access_rows import Caller as ApiCaller
from scripts.access_table import (
    PAGE_ROW_MODULES,
    REVIEW_PATH,
    current_tables,
    render_api_table,
    render_fhir_table,
    render_page_table,
    render_section,
    splice,
)
from test_support.fhir_access_rows import FhirAccessRow

PAGE_DIRECTORY = Path(__file__).resolve().parent.parent / "scheduling" / "views" / "pages"
ACCESS_SECTION = "## Access\n\nold text\n\n"
SECTION_AFTER = "## Section 4: rules that apply everywhere\n\nrule text\n"


def returns_unchanged_document_when_section_is_current() -> None:
    document = REVIEW_PATH.read_text(encoding="utf-8")

    assert splice(document, render_section(current_tables())) == document


def returns_changed_document_when_table_row_differs() -> None:
    document = REVIEW_PATH.read_text(encoding="utf-8")
    tables = current_tables()
    changed_row = replace(tables.api_rows[0], visitor=403)

    changed = replace(tables, api_rows=(changed_row,) + tables.api_rows[1:])

    assert splice(document, render_section(changed)) != document


def raises_value_error_when_access_heading_is_missing() -> None:
    with pytest.raises(ValueError, match="## Access"):
        splice("# Title\n\n## Other\n", ACCESS_SECTION)


def raises_value_error_when_access_heading_appears_twice() -> None:
    document = ACCESS_SECTION + ACCESS_SECTION

    with pytest.raises(ValueError, match="## Access"):
        splice(document, ACCESS_SECTION)


def returns_section_to_end_of_file_when_no_later_heading_follows() -> None:
    document = "# Title\n\n" + ACCESS_SECTION

    assert splice(document, "## Access\n\nnew\n\n") == "# Title\n\n## Access\n\nnew\n\n"


def returns_text_outside_section_unchanged_when_splicing() -> None:
    document = "# Title\n\nintro\n\n" + ACCESS_SECTION + SECTION_AFTER

    result = splice(document, "## Access\n\nnew\n\n")

    assert result.startswith("# Title\n\nintro\n\n## Access\n\nnew\n\n")
    assert result.endswith(SECTION_AFTER)


def returns_escaped_pipe_when_cell_holds_pipe() -> None:
    rows = (AccessRow("GET", "api/v1/x", 200, 200, 200, 200, "a|b"),)

    assert "a\\|b" in render_api_table(rows, ())


def returns_leading_slash_route_when_stored_route_has_none() -> None:
    page = render_page_table((Row("", OK, OK, OK, OK),), {})
    api = render_api_table((AccessRow("GET", "api/v1/health", 200, 200, 200, 200, ""),), ())

    assert "| `/` |" in page
    assert "`/api/v1/health`" in api


def returns_both_answers_when_page_difference_listed() -> None:
    differences: dict[tuple[str, Caller], tuple[Answer, str]] = {
        ("favicon.ico", "visitor"): (Answer.OK, "302 /static/favicon.svg"),
    }

    text = render_page_table((), differences)

    assert "`/favicon.ico`, visitor: table `ok`, product `302 /static/favicon.svg`" in text


def returns_record_phrase_when_api_difference_names_own_record() -> None:
    difference = KnownDifference(ApiCaller.VISITOR, "GET", "api/v1/x", RecordUse.OWN, 401, 200)

    text = render_api_table((), (difference,))

    assert "`GET /api/v1/x`, visitor, own record: table `401`, product `200`" in text


def returns_no_record_phrase_when_difference_names_no_record() -> None:
    difference = KnownDifference(ApiCaller.PATIENT, "POST", "api/v1/x", None, 403, 200)

    text = render_api_table((), (difference,))

    assert "`POST /api/v1/x`, patient: table `403`, product `200`" in text
    assert "record:" not in text


def returns_none_line_when_surface_has_no_known_differences() -> None:
    api = render_api_table((), ())
    fhir = render_fhir_table((FhirAccessRow("Slot", "read", 200, 200, 200, 200, "x"),), ())

    assert "Known differences: none." in api
    assert "Known differences: none." in fhir


def returns_five_page_modules_when_glob_lists_access_row_files() -> None:
    listed = sorted(path.name for path in PAGE_DIRECTORY.glob("test_page_access_rows*.py"))
    imported = sorted(module.__name__.rsplit(".", 1)[-1] + ".py" for module in PAGE_ROW_MODULES)

    assert len(imported) == 5
    assert listed == imported
