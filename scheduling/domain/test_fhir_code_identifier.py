"""Section 15.2: the unique code a client reads and sends back on any record resource."""

from datetime import UTC, datetime
from uuid import uuid4

from scheduling.domain.failure import Failure
from scheduling.domain.fhir_common import CODE_IDENTIFIER_SYSTEM, code_identifier
from scheduling.domain.fhir_location import RoomSource, SiteSource, room_location, site_location
from scheduling.domain.fhir_organization import OrganizationSource, department_organization
from scheduling.domain.fhir_outcome import failure_outcome
from scheduling.domain.fhir_service import ServiceSource, healthcare_service

STAMP = datetime(2026, 1, 1, tzinfo=UTC)
EXPECTED = [{"system": CODE_IDENTIFIER_SYSTEM, "value": "the-code"}]


def returns_system_and_value_when_a_code_is_given() -> None:
    assert code_identifier("the-code") == {"identifier": EXPECTED}


def returns_nothing_when_no_code_is_given() -> None:
    assert code_identifier("") == {}


def returns_the_code_as_identifier_when_a_site_has_one() -> None:
    source = SiteSource(
        uuid4(), "n", 1, STAMP, True, "s", "p", "c", "k", "ph", "UTC", None, None, "the-code"
    )

    assert site_location(source)["identifier"] == EXPECTED


def returns_the_code_as_identifier_when_a_room_has_one() -> None:
    source = RoomSource(uuid4(), "n", 1, STAMP, True, uuid4(), uuid4(), "1", 2, (), "the-code")

    assert room_location(source)["identifier"] == EXPECTED


def returns_the_code_as_identifier_when_a_department_has_one() -> None:
    source = OrganizationSource(uuid4(), "n", 1, STAMP, True, uuid4(), "the-code")

    assert department_organization(source)["identifier"] == EXPECTED


def returns_the_code_as_identifier_when_a_service_has_one() -> None:
    source = ServiceSource(
        uuid4(), "n", 1, STAMP, True, uuid4(), 30, 0, "#112233", True, True, (), "the-code"
    )

    assert healthcare_service(source)["identifier"] == EXPECTED


def returns_what_still_uses_the_record_in_the_diagnostics_when_it_has_dependents() -> None:
    failure = Failure.has_dependents(["2 departments", "1 room"])

    issue = failure_outcome(failure, "t", "abc")["issue"][0]  # type: ignore[index]

    assert issue["diagnostics"] == "abc Still used by: 2 departments, 1 room."


def returns_only_the_correlation_id_in_the_diagnostics_when_a_failure_has_no_dependents() -> None:
    issue = failure_outcome(Failure.not_found(), "t", "abc")["issue"][0]  # type: ignore[index]

    assert issue["diagnostics"] == "abc"
