"""Task 19 item 17: a list page is counted and cut in the database, not in Python."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.models.builders import make
from scheduling.use_cases.admin_record_reads import list_records

pytestmark = pytest.mark.django_db

MODELS = {
    "hospital": "Hospital",
    "specialty": "Specialty",
    "department": "Department",
    "room": "Room",
    "appointment_type": "AppointmentType",
}


@pytest.mark.parametrize("kind", sorted(MODELS))
def returns_twenty_of_twenty_five_rows_in_two_queries_when_a_list_is_read(kind: str) -> None:
    for _ in range(25):
        make(MODELS[kind])

    with CaptureQueriesContext(connection) as queries:
        page = list_records(kind, "", 1)

    assert (page.total, len(page.items), page.page_count, len(queries)) == (25, 20, 2, 2)


@pytest.mark.parametrize("kind", sorted(MODELS))
def returns_the_same_number_of_queries_when_the_list_holds_one_row_or_twenty(kind: str) -> None:
    make(MODELS[kind])
    with CaptureQueriesContext(connection) as one_row:
        list_records(kind, "", 1)
    for _ in range(19):
        make(MODELS[kind])

    with CaptureQueriesContext(connection) as twenty_rows:
        list_records(kind, "", 1)

    assert len(twenty_rows) == len(one_row)


@pytest.mark.parametrize("kind", sorted(MODELS))
def returns_the_last_five_rows_when_page_two_of_twenty_five_is_read(kind: str) -> None:
    for _ in range(25):
        make(MODELS[kind])

    page = list_records(kind, "", 2)

    assert (page.page, len(page.items)) == (2, 5)


@pytest.mark.parametrize("kind", sorted(MODELS))
def returns_rows_whose_parent_is_already_loaded_when_a_list_is_read(kind: str) -> None:
    from scheduling.use_cases.admin_record_specs import SPECS

    parent = SPECS[kind].parent_form_name
    for _ in range(5):
        make(MODELS[kind])

    with CaptureQueriesContext(connection) as queries:
        page = list_records(kind, "", 1)
        if parent:
            [getattr(row, parent).pk for row in page.items]

    assert len(queries) == 2
