"""Task 22a, point 10: the database counts and cuts the page; no query loads every match."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Success
from scheduling.domain.fhir_search import SearchQuery
from scheduling.models.builders import make
from scheduling.use_cases.fhir_reads import Viewer, search_resource

pytestmark = pytest.mark.django_db

HOSPITALS = 7


def returns_second_page_and_full_total_when_database_cuts_the_page() -> None:
    for number in range(HOSPITALS):
        make("Hospital", name=f"Hospital {number}")
    query = SearchQuery((), 2, 2, "name", False, ())

    with CaptureQueriesContext(connection) as queries:
        result = search_resource("Location", query, Viewer.PUBLIC)

    assert isinstance(result, Success)
    assert result.value.total == HOSPITALS
    assert [item["name"] for item in result.value.matches] == ["Hospital 2", "Hospital 3"]
    statements = [item["sql"] for item in queries.captured_queries]
    assert any("LIMIT 2 OFFSET 2" in sql for sql in statements)
    assert any("COUNT" in sql for sql in statements)
