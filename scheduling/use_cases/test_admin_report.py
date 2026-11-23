"""Section 13: an appointment counts on its hospital's local date, zones on both sides of UTC."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.models import AppointmentType, Department
from scheduling.models.builders import Clinic, add_clinician, make, make_user
from scheduling.use_cases.admin_report import Report, build_report
from scheduling.use_cases.request_context import bind_request_context

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
SYDNEY = "Australia/Sydney"
NEW_YORK = "America/New_York"


def _clinic_in(time_zone: str) -> Clinic:
    hospital = make("Hospital", time_zone=time_zone)
    department = make("Department", hospital=hospital)
    appointment_type = make("AppointmentType", department=department)
    assert isinstance(department, Department) and isinstance(appointment_type, AppointmentType)
    return Clinic(department, appointment_type, add_clinician(department), make_user())


def _book_local(clinic: Clinic, local_start: datetime) -> None:
    starts_at = local_start.replace(tzinfo=ZoneInfo(clinic.department.hospital.time_zone))
    make(
        "Appointment",
        patient=clinic.patient,
        clinician=clinic.clinician,
        appointment_type=clinic.appointment_type,
        starts_at=starts_at.astimezone(UTC),
        ends_at=starts_at.astimezone(UTC) + timedelta(minutes=30),
    )


def _report() -> Report:
    with bind_request_context(RequestContext(correlation_id="c", now=NOW)):
        return build_report("7")


def _counted_per_day(report: Report) -> dict[date, int]:
    return {row.day: row.count for row in report.per_day if row.count}


@pytest.mark.parametrize(
    ("time_zone", "local_start", "expected_day"),
    [
        (SYDNEY, datetime(2026, 11, 24, 0, 0), date(2026, 11, 24)),
        (SYDNEY, datetime(2026, 11, 23, 23, 59), date(2026, 11, 23)),
        (SYDNEY, datetime(2026, 11, 18, 0, 0), date(2026, 11, 18)),
        (NEW_YORK, datetime(2026, 11, 24, 0, 0), date(2026, 11, 24)),
        (NEW_YORK, datetime(2026, 11, 23, 23, 59), date(2026, 11, 23)),
        (NEW_YORK, datetime(2026, 11, 24, 23, 59), date(2026, 11, 24)),
    ],
)
def returns_the_hospital_day_when_the_start_is_near_midnight(
    time_zone: str, local_start: datetime, expected_day: date
) -> None:
    _book_local(_clinic_in(time_zone), local_start)

    assert _counted_per_day(_report()) == {expected_day: 1}


def returns_both_appointments_on_their_hospital_day_when_zones_lie_on_both_sides_of_utc() -> None:
    _book_local(_clinic_in(SYDNEY), datetime(2026, 11, 24, 0, 30))
    _book_local(_clinic_in(NEW_YORK), datetime(2026, 11, 24, 23, 30))

    report = _report()

    assert _counted_per_day(report) == {date(2026, 11, 24): 2}
    assert report.appointments == 2


def returns_no_count_when_the_hospital_day_lies_before_the_range() -> None:
    _book_local(_clinic_in(SYDNEY), datetime(2026, 11, 17, 23, 59))

    report = _report()

    assert _counted_per_day(report) == {}
    assert report.appointments == 0
