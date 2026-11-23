"""Section 15.3: every appointment status and every waitlist status read through FHIR as
the section's tables say. The expected values are the specification's, held here as data."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus
from scheduling.models import Appointment, WaitlistEntry
from scheduling.models.builders import STARTS_AT, Clinic, make, make_clinic
from scheduling.use_cases.test_waitlist_support import _cancelled_slot, _offered_entry
from scheduling.views import clock
from scheduling.views.fhir_test_support import NOW, extension, get, token_of

pytestmark = pytest.mark.django_db

STATUS_EXTENSION = "appointment-status"
REASON = "Cannot come"
HALF_HOUR = timedelta(minutes=30)


@dataclass(frozen=True)
class Row:
    """One line of a table of 15.3: the stored status, the FHIR status, what else is promised."""

    table: str
    stored: str
    fhir: str
    kept_internal_value: str = ""
    cancelation_reason: bool = False
    offer: bool = False


SPEC_ROWS = (
    Row("appointment", "BOOKED", "booked", kept_internal_value="booked"),
    Row("appointment", "CONFIRMED", "booked", kept_internal_value="confirmed"),
    Row("appointment", "CHECKED_IN", "checked-in"),
    Row("appointment", "COMPLETED", "fulfilled"),
    Row("appointment", "CANCELLED", "cancelled", cancelation_reason=True),
    Row("appointment", "NO_SHOW", "noshow"),
    Row("waitlist", "WAITING", "waitlist"),
    Row("waitlist", "OFFERED", "proposed", offer=True),
    Row("waitlist", "BOOKED", "booked", kept_internal_value="booked"),
    Row("waitlist", "EXPIRED", "cancelled"),
)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _stored_id(clinic: Clinic, row: Row) -> str:
    if row.table == "appointment":
        fields = (
            {"cancellation_reason": REASON, "cancelled_at": NOW} if row.cancelation_reason else {}
        )
        appointment = make(
            "Appointment",
            clinician=clinic.clinician,
            appointment_type=clinic.appointment_type,
            patient=clinic.patient,
            status=row.stored,
            **fields,
        )
        assert isinstance(appointment, Appointment)
        return str(appointment.pk)
    if row.offer:
        entry = _offered_entry(clinic, _cancelled_slot(clinic))
        return str(entry.pk)
    waiting = make(
        "WaitlistEntry",
        patient=clinic.patient,
        appointment_type=clinic.appointment_type,
        status=row.stored,
    )
    assert isinstance(waiting, WaitlistEntry)
    if row.stored == "BOOKED":
        make(
            "Appointment",
            clinician=clinic.clinician,
            appointment_type=clinic.appointment_type,
            patient=clinic.patient,
            waitlist_entry=waiting,
        )
    return str(waiting.pk)


def _internal_value(body: dict[str, object]) -> str:
    url = extension(STATUS_EXTENSION)["url"]
    found = [item for item in body.get("extension", []) if item["url"] == url]  # type: ignore[attr-defined]
    return str(found[0]["valueCode"]) if found else ""


def returns_the_covered_statuses_when_the_tables_of_15_3_are_compared_with_the_vocabulary() -> None:
    appointment = {row.stored for row in SPEC_ROWS if row.table == "appointment"}
    waitlist = {row.stored for row in SPEC_ROWS if row.table == "waitlist"}

    assert appointment == {item.value for item in AppointmentStatus}
    assert waitlist == {item.value for item in WaitlistStatus}


@pytest.mark.parametrize("row", SPEC_ROWS, ids=lambda row: f"{row.table}-{row.stored}")
def returns_the_mapped_appointment_status_for_every_appointment_and_waitlist_status(
    row: Row,
) -> None:
    clinic = make_clinic()
    key = _stored_id(clinic, row)

    response = get(f"/fhir/Appointment/{key}", token_of(clinic.patient))

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == row.fhir
    assert _internal_value(body) == row.kept_internal_value
    assert ("cancelationReason" in body) is row.cancelation_reason
    if row.cancelation_reason:
        assert body["cancelationReason"] == {"text": REASON}
    if row.offer:
        assert datetime.fromisoformat(body["start"]) == STARTS_AT
        assert datetime.fromisoformat(body["end"]) == STARTS_AT + HALF_HOUR
        assert f"Practitioner/{clinic.clinician.user_id}" in str(body["participant"])
