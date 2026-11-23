"""Section 6: public reads that compute schedules share one counter per caller
(1200 an hour), anonymous FHIR reads another (600). A caller with a session or a token is counted
by user id, never against its address."""

from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from scheduling.models.builders import make, make_clinic
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client, fhir_client
from scheduling.views.fhir_test_support import token_of
from scheduling.views.pages.admin_support import client_of_role
from scheduling.views.pages.booking_pages_support import details_path, times_path
from scheduling.views.pages.search_pages_support import plant_clinic

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SCHEDULE_READS_PER_HOUR = 1200
FHIR_READS_PER_HOUR = 600
OTHER_ADDRESS = "198.51.100.77"
PROVIDERS_IN_A_WALK = 8
WEEKS_IN_A_WALK = 4
HOUR = timedelta(hours=1)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    instant = [NOW]
    monkeypatch.setattr(clock, "now_utc", lambda: instant[0])
    return instant


def _read(client: Client, path: str, **extra: str) -> int:
    return client.get(path, **extra).status_code  # type: ignore[arg-type]


def _fill(client: Client, path: str, count: int, **extra: str) -> list[int]:
    return [_read(client, path, **extra) for _ in range(count)]


def _paths() -> dict[str, str]:
    clinic = make_clinic()
    hospital = clinic.department.hospital
    specialty = make("Specialty")
    type_id, provider_id = clinic.appointment_type.pk, clinic.clinician.pk
    slots = f"appointment_type_id={type_id}&from=2030-01-07T00:00:00Z&to=2030-01-08T00:00:00Z"
    return {
        "provider_page": f"/providers/{provider_id}",
        "hospital_page": f"/hospitals/{hospital.pk}",
        "specialty_page": f"/specialties/{specialty.pk}",
        "provider_api": f"/api/v1/providers/{provider_id}",
        "hospital_api": f"/api/v1/hospitals/{hospital.pk}",
        "specialty_api": f"/api/v1/specialties/{specialty.pk}",
        "slots_api": f"/api/v1/slots?{slots}",
        "book_services": "/book",
        "book_providers": f"/book/{type_id}/provider",
        "book_times": times_path(clinic),
        "book_details": details_path(clinic),
    }


ROUTES = [
    "provider_page", "hospital_page", "specialty_page", "provider_api", "hospital_api",
    "specialty_api", "slots_api", "book_services", "book_providers", "book_times", "book_details",
]  # fmt: skip


def returns_429_with_retry_after_when_one_address_reads_1201_provider_pages_in_an_hour() -> None:
    path = _paths()["provider_page"]
    client = browser_api_client(raise_request_exception=False)

    statuses = _fill(client, path, SCHEDULE_READS_PER_HOUR + 1)

    assert set(statuses[:SCHEDULE_READS_PER_HOUR]) == {200}
    assert statuses[SCHEDULE_READS_PER_HOUR] == 429


@pytest.mark.parametrize("route", ROUTES)
def returns_429_on_every_schedule_route_when_the_shared_counter_is_full(route: str) -> None:
    paths = _paths()
    client = browser_api_client(raise_request_exception=False)
    _fill(client, paths["provider_api"], SCHEDULE_READS_PER_HOUR)

    response = client.get(paths[route])

    assert response.status_code == 429
    assert int(response["Retry-After"]) >= 1


def returns_200_for_every_read_when_a_person_walks_eight_providers_with_four_weeks_each() -> None:
    clinics = [make_clinic() for _ in range(PROVIDERS_IN_A_WALK)]
    client = browser_api_client(raise_request_exception=False)
    statuses = []
    for clinic in clinics:
        statuses.append(_read(client, f"/providers/{clinic.clinician.pk}"))
        for week in range(WEEKS_IN_A_WALK):
            query = f"?provider={clinic.clinician.pk}&week=2030-01-{7 + 7 * week:02d}"
            statuses.append(_read(client, times_path(clinic, query)))
        statuses.append(_read(client, details_path(clinic)))

    assert set(statuses) == {200}


def returns_200_when_another_address_reads_after_the_first_is_limited() -> None:
    path = _paths()["provider_api"]
    client = browser_api_client(raise_request_exception=False)
    _fill(client, path, SCHEDULE_READS_PER_HOUR + 1)

    assert _read(client, path, REMOTE_ADDR=OTHER_ADDRESS) == 200


def returns_200_again_when_an_hour_has_passed(frozen_clock: list[datetime]) -> None:
    path = _paths()["provider_api"]
    client = browser_api_client(raise_request_exception=False)
    _fill(client, path, SCHEDULE_READS_PER_HOUR + 1)
    frozen_clock[0] = NOW + HOUR + timedelta(seconds=1)

    assert _read(client, path) == 200


def returns_limited_page_with_header_footer_and_try_again_link_when_a_page_is_limited() -> None:
    path = _paths()["provider_page"]
    client = browser_api_client(raise_request_exception=False)
    _fill(client, path, SCHEDULE_READS_PER_HOUR)

    response = client.get(path)

    html = response.content.decode()
    assert response.status_code == 429
    assert int(response["Retry-After"]) >= 1
    assert "<header" in html
    assert "<footer" in html
    assert f'href="{path}"' in html


def returns_operation_outcome_throttled_when_anonymous_fhir_read_is_limited() -> None:
    clinician, _ = plant_clinic()
    client = fhir_client()
    path = f"/fhir/Organization/{clinician.department.hospital.pk}"
    _fill(client, path, FHIR_READS_PER_HOUR)

    response = client.get(path)

    assert response.status_code == 429
    assert response["Content-Type"].startswith("application/fhir+json")
    assert response.json()["resourceType"] == "OperationOutcome"
    assert response.json()["issue"][0]["code"] == "throttled"
    assert int(response["Retry-After"]) >= 1


def returns_200_for_fhir_metadata_when_the_fhir_counter_is_full() -> None:
    client = fhir_client()
    _fill(client, "/fhir/Organization", FHIR_READS_PER_HOUR)

    assert _read(client, "/fhir/metadata") == 200


def returns_200_when_staff_with_sessions_behind_one_address_read_more_than_one_user_may() -> None:
    path = _paths()["provider_api"]
    first, second = client_of_role("ADMIN"), client_of_role("ADMIN")
    _fill(browser_api_client(), path, SCHEDULE_READS_PER_HOUR)

    assert [_read(first, path), _read(second, path)] == [200, 200]


def returns_200_when_staff_read_pages_behind_one_address_whose_counter_is_full() -> None:
    path = _paths()["provider_page"]
    first, second = client_of_role("ADMIN"), client_of_role("ADMIN")
    _fill(browser_api_client(), path, SCHEDULE_READS_PER_HOUR)

    assert [_read(first, path), _read(second, path)] == [200, 200]


def returns_429_when_one_signed_in_user_reads_1201_times() -> None:
    path = _paths()["provider_api"]
    client = client_of_role("ADMIN")

    statuses = _fill(client, path, SCHEDULE_READS_PER_HOUR + 1)

    assert set(statuses[:SCHEDULE_READS_PER_HOUR]) == {200}
    assert statuses[SCHEDULE_READS_PER_HOUR] == 429


def returns_200_when_a_token_holder_reads_while_the_address_counter_is_full() -> None:
    clinician, _ = plant_clinic()
    path = f"/fhir/Organization/{clinician.department.hospital.pk}"
    _fill(fhir_client(), path, FHIR_READS_PER_HOUR)

    assert _read(fhir_client(token_of()), path) == 200


PAGE_SCHEDULE_ROUTES = [
    "provider_page", "hospital_page", "specialty_page", "book_services", "book_providers",
    "book_times", "book_details",
]  # fmt: skip
API_SCHEDULE_ROUTES = ["provider_api", "hospital_api", "specialty_api", "slots_api"]
ANONYMOUS_FHIR_READ = "/fhir/Location"


def _heads(client: Client, path: str, count: int) -> list[int]:
    return [client.head(path).status_code for _ in range(count)]


@pytest.mark.parametrize("route", PAGE_SCHEDULE_ROUTES)
def returns_429_with_retry_after_when_head_requests_fill_the_schedule_counter(route: str) -> None:
    path = _paths()[route]
    client = browser_api_client(raise_request_exception=False)

    head_statuses = _heads(client, path, SCHEDULE_READS_PER_HOUR)
    limited_head = client.head(path)
    limited_get = client.get(path)

    assert set(head_statuses) == {200}
    assert limited_head.status_code == 429
    assert int(limited_head["Retry-After"]) >= 1
    assert limited_get.status_code == 429
    assert int(limited_get["Retry-After"]) >= 1


@pytest.mark.parametrize("route", API_SCHEDULE_ROUTES)
def returns_404_and_counts_nothing_when_head_reaches_an_api_schedule_read(route: str) -> None:
    path = _paths()[route]
    client = browser_api_client(raise_request_exception=False)

    head_statuses = _heads(client, path, SCHEDULE_READS_PER_HOUR)
    get_statuses = _fill(client, path, SCHEDULE_READS_PER_HOUR)

    assert set(head_statuses) == {404}
    assert set(get_statuses) == {200}


def returns_405_and_counts_nothing_when_head_reaches_an_anonymous_fhir_read() -> None:
    client = fhir_client()

    head_statuses = _heads(client, ANONYMOUS_FHIR_READ, FHIR_READS_PER_HOUR)
    get_statuses = _fill(client, ANONYMOUS_FHIR_READ, FHIR_READS_PER_HOUR)

    assert set(head_statuses) == {405}
    assert set(get_statuses) == {200}
