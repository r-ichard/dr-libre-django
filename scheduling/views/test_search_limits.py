"""Section 6: public search is limited per network address (120 an hour, the mechanism of
task 12) and its query count does not grow with the catalogue. The address is REMOTE_ADDR, so
callers behind one proxy share a count; proxy trust is task 26."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.models.builders import add_clinician, make
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client
from scheduling.views.pages.search_pages_support import HOUR_OF_SLOTS

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SEARCHES_PER_HOUR = 120
OTHER_ADDRESS = "198.51.100.77"
SMALL_CATALOGUE = 3
LARGE_CATALOGUE = 30


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    instant = [NOW]
    monkeypatch.setattr(clock, "now_utc", lambda: instant[0])
    return instant


def _searches(count: int, **extra: str) -> list[int]:
    client = browser_api_client()
    return [
        client.get("/api/v1/search/providers", **extra).status_code  # type: ignore[arg-type]
        for _ in range(count)
    ]


def returns_429_when_address_searches_121_times_in_an_hour_through_the_api(
    frozen_clock: list[datetime],
) -> None:
    statuses = _searches(SEARCHES_PER_HOUR + 1)

    assert statuses[:SEARCHES_PER_HOUR] == [200] * SEARCHES_PER_HOUR
    assert statuses[SEARCHES_PER_HOUR] == 429


def returns_429_when_address_searches_121_times_in_an_hour_through_the_page(
    frozen_clock: list[datetime],
) -> None:
    client = browser_api_client()
    statuses = [client.get("/?q=heart").status_code for _ in range(SEARCHES_PER_HOUR + 1)]

    assert statuses[SEARCHES_PER_HOUR] == 429
    assert set(statuses[:SEARCHES_PER_HOUR]) == {200}


def returns_200_when_a_different_address_searches_after_the_first_is_limited(
    frozen_clock: list[datetime],
) -> None:
    _searches(SEARCHES_PER_HOUR + 1)

    assert _searches(1, REMOTE_ADDR=OTHER_ADDRESS) == [200]


def returns_200_again_when_an_hour_has_passed_since_the_limit(
    frozen_clock: list[datetime],
) -> None:
    _searches(SEARCHES_PER_HOUR + 1)
    frozen_clock[0] = NOW + timedelta(hours=1, seconds=1)

    assert _searches(1) == [200]


def _grow_catalogue(size: int) -> None:
    hospital = make("Hospital")
    department = make("Department", hospital=hospital)
    make("AppointmentType", department=department)
    for _ in range(size):
        add_clinician(department, HOUR_OF_SLOTS)


def _query_count(path: str) -> int:
    with CaptureQueriesContext(connection) as queries:
        assert browser_api_client().get(path).status_code == 200  # noqa: S101 - a broken page is a broken test
    return len(queries)


@pytest.mark.parametrize(
    "path", ["/", "/?q=a", "/api/v1/search/providers", "/api/v1/search/hospitals"]
)
def returns_same_query_count_when_catalogue_holds_3_or_30_clinicians(
    frozen_clock: list[datetime], path: str
) -> None:
    _grow_catalogue(SMALL_CATALOGUE)
    small = _query_count(path)
    _grow_catalogue(LARGE_CATALOGUE - SMALL_CATALOGUE)

    assert _query_count(path) == small
