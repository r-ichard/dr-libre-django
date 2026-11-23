"""Checking a form that is not saved takes no row lock."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.models.builders import make
from scheduling.use_cases.admin_clinicians import reference_messages

pytestmark = pytest.mark.django_db


def returns_no_for_update_query_when_a_form_is_checked_without_saving() -> None:
    department = make("Department")
    values = {
        "department_id": department.pk,
        "specialty_id": make("Specialty").pk,
        "default_room_id": make("Room", department=department).pk,
    }

    with CaptureQueriesContext(connection) as captured:
        messages = reference_messages(values, None)

    assert messages == {}
    assert len(captured) >= 3
    assert not [query for query in captured if "FOR UPDATE" in query["sql"]]
