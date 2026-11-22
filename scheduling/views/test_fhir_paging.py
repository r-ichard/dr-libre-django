"""Task 23a, point 13: a link the server writes is a request the server accepts. Following `next`
from the first page collects exactly `total` entries, each once."""

import pytest

from scheduling.domain.fhir_declaration import FHIR_RESOURCES
from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, get, token_of

pytestmark = pytest.mark.django_db

SEARCHABLE = sorted(
    declaration.type for declaration in FHIR_RESOURCES if "search-type" in declaration.interactions
)
SORTED_SEARCHES = [
    (declaration.type, f"{prefix}{name}")
    for declaration in FHIR_RESOURCES
    if "search-type" in declaration.interactions
    for name in declaration.sortable
    for prefix in ("", "-")
]


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _path_of(url: str) -> str:
    return "/fhir" + url.split("/fhir", 1)[1]


@pytest.mark.parametrize(
    ("resource", "sort"),
    [(resource, "") for resource in SEARCHABLE] + SORTED_SEARCHES,
)
def returns_every_entry_once_when_next_is_followed_to_the_last_page(
    resource: str, sort: str
) -> None:
    clinic = make_clinic(rule_fields={"weekday": 1})
    for _ in range(3):
        make(
            "Appointment",
            clinician=clinic.clinician,
            appointment_type=clinic.appointment_type,
            starts_at=NOW.replace(day=14 + _),
            ends_at=NOW.replace(day=14 + _, minute=30),
        )
    extra = (
        f"&service-type={clinic.appointment_type.pk}&start=ge2030-01-07T00:00:00Z&start=lt2030-01-08T00:00:00Z"
        if resource == "Slot"
        else ""
    )
    token = token_of(role="ADMIN")
    order = f"&_sort={sort}" if sort else ""
    response = get(f"/fhir/{resource}?_count=2{extra}{order}", token)
    assert response.status_code == 200
    total = response.json()["total"]
    seen = [item["resource"]["id"] for item in response.json().get("entry", [])]

    links = {link["relation"]: link["url"] for link in response.json()["link"]}
    again = get(_path_of(links["self"]), token)
    assert again.json().get("entry") == response.json().get("entry")
    while "next" in links:
        page = get(_path_of(links["next"]), token)
        assert page.status_code == 200
        seen += [item["resource"]["id"] for item in page.json().get("entry", [])]
        links = {link["relation"]: link["url"] for link in page.json()["link"]}

    assert sorted(seen) == sorted(set(seen))
    assert len(seen) == total
