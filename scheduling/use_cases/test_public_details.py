"""Task 11: the three public details answer not found for anything search would not list, and the
cost of a hospital does not grow with its providers."""

from collections.abc import Iterator
from datetime import UTC, datetime, time
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from scheduling.domain.failure import Failure, FailureCode, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import ClinicianProfile, Department
from scheduling.models.builders import add_clinician, make
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
HOUR_OF_SLOTS = {"start_time": time(11, 0), "end_time": time(12, 0), "slot_step_minutes": 30}
QUERY_CEILING = 14


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-details", NOW)):
        yield


def _department(**hospital: object) -> Department:
    department = make("Department", hospital=make("Hospital", **hospital))
    assert isinstance(department, Department)
    return department


def _listable_clinician(department: Department, name: str = "Vera Visible") -> ClinicianProfile:
    make("AppointmentType", department=department)
    user = make("User", role="CLINICIAN", full_name=name)
    return add_clinician(department, HOUR_OF_SLOTS, user=user)


def _not_found(result: object) -> bool:
    return isinstance(result, Failure) and result.code == FailureCode.NOT_FOUND


def returns_success_when_provider_is_listable() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    clinician = _listable_clinician(_department())

    result = load_provider_detail(clinician.pk, None, NOW)

    assert isinstance(result, Success)


def returns_not_found_when_provider_id_is_unknown() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    assert _not_found(load_provider_detail(uuid4(), None, NOW))


def returns_not_found_when_provider_user_inactive() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    clinician = _listable_clinician(_department())
    clinician.user.refresh_from_db()
    clinician.user.is_active = False
    clinician.user.save()

    assert _not_found(load_provider_detail(clinician.pk, None, NOW))


def returns_not_found_when_provider_hospital_inactive() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    clinician = _listable_clinician(_department(is_active=False))

    assert _not_found(load_provider_detail(clinician.pk, None, NOW))


def returns_not_found_when_provider_specialty_inactive() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    department = _department()
    make("AppointmentType", department=department)
    user = make("User", role="CLINICIAN", full_name="Sam Specialty")
    specialty = make("Specialty", is_active=False)
    clinician = add_clinician(department, HOUR_OF_SLOTS, user=user, specialty=specialty)

    assert _not_found(load_provider_detail(clinician.pk, None, NOW))


def returns_not_found_when_provider_department_has_no_online_bookable_type() -> None:
    from scheduling.use_cases.public_details import load_provider_detail

    department = _department()
    make("AppointmentType", department=department, is_bookable_online=False)
    clinician = add_clinician(department, HOUR_OF_SLOTS)

    assert _not_found(load_provider_detail(clinician.pk, None, NOW))


def returns_not_found_when_hospital_inactive() -> None:
    from scheduling.use_cases.public_details import load_hospital_detail

    department = _department(is_active=False)
    _listable_clinician(department)

    assert _not_found(load_hospital_detail(department.hospital.pk, NOW))


def returns_not_found_when_hospital_id_is_unknown() -> None:
    from scheduling.use_cases.public_details import load_hospital_detail

    assert _not_found(load_hospital_detail(uuid4(), NOW))


def returns_success_when_hospital_has_no_bookable_provider() -> None:
    from scheduling.use_cases.public_details import load_hospital_detail

    department = _department()

    assert isinstance(load_hospital_detail(department.hospital.pk, NOW), Success)


def returns_not_found_when_specialty_inactive() -> None:
    from scheduling.use_cases.public_details import load_specialty_detail

    specialty = make("Specialty", is_active=False)

    assert _not_found(load_specialty_detail(specialty.pk, 1, NOW))


def returns_not_found_when_specialty_id_is_unknown() -> None:
    from scheduling.use_cases.public_details import load_specialty_detail

    assert _not_found(load_specialty_detail(uuid4(), 1, NOW))


def returns_success_when_specialty_has_no_provider() -> None:
    from scheduling.use_cases.public_details import load_specialty_detail

    specialty = make("Specialty")

    assert isinstance(load_specialty_detail(specialty.pk, 1, NOW), Success)


def _add_clinicians(department: Department, count: int) -> None:
    for number in range(count):
        _listable_clinician(department, f"Doc {uuid4().hex[:6]} {number}")


def returns_same_number_of_queries_when_hospital_has_2_or_12_providers() -> None:
    from scheduling.use_cases.public_details import load_hospital_detail

    department = _department()
    hospital_id = department.hospital.pk
    _add_clinicians(department, 2)
    with CaptureQueriesContext(connection) as few:
        load_hospital_detail(hospital_id, NOW)
    _add_clinicians(department, 10)

    with CaptureQueriesContext(connection) as many:
        load_hospital_detail(hospital_id, NOW)

    assert len(many) == len(few)
    assert len(many) <= QUERY_CEILING


def returns_departments_and_specialties_by_name_and_first_available_by_department() -> None:
    from scheduling.use_cases.public_details import load_hospital_detail

    hospital = make("Hospital")
    kinds = {}
    for name in ("Zeta Ward", "Alpha Ward"):
        department = make("Department", hospital=hospital, name=name)
        kinds[name] = make("AppointmentType", department=department, name="Check-up")
        user = make("User", role="CLINICIAN", full_name=f"Doc {name}")
        add_clinician(department, HOUR_OF_SLOTS, user=user)

    loaded = load_hospital_detail(hospital.pk, NOW)

    assert isinstance(loaded, Success)
    detail = loaded.value
    assert [item.name for item in detail.departments] == ["Alpha Ward", "Zeta Ward"]
    names = [item.name for item in detail.specialties]
    assert names == sorted(names, key=str.casefold)
    assert len(names) == 2
    assert [(c.department_name, c.appointment_type.id) for c in detail.first_available] == [
        ("Alpha Ward", kinds["Alpha Ward"].pk),
        ("Zeta Ward", kinds["Zeta Ward"].pk),
    ]
