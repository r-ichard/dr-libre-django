"""Time off through FHIR `PractitionerRole.notAvailable.during`, sent as a FHIR client
sends it (bearer token, no cookie, no Origin). Values from spec 15.2, 15.4, R4, ADR 0009:
a stored period is repeated, never edited."""

from datetime import UTC, datetime, time, timedelta

import pytest

from scheduling.models import TimeOff
from scheduling.models.builders import make_clinic, make_user
from scheduling.views import clock
from scheduling.views.fhir_role_support import element_names, period, stored_role
from scheduling.views.fhir_test_support import NOW, get, send, token_of

pytestmark = pytest.mark.django_db

HOURS = {"start_time": time(11, 0), "end_time": time(13, 0), "slot_step_minutes": 30}
FIRST = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
HALF_HOUR = timedelta(minutes=30)
ALL_FOUR = [FIRST + step * HALF_HOUR for step in range(4)]
DAY_RANGE = "2030-01-07T00:00:00Z", "2030-01-08T00:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _api_starts(clinic: object) -> list[datetime]:
    type_id = clinic.appointment_type.pk  # type: ignore[attr-defined]
    clinician_id = clinic.clinician.pk  # type: ignore[attr-defined]
    query = f"appointment_type_id={type_id}&clinician_id={clinician_id}"
    response = get(f"/api/v1/slots?{query}&from={DAY_RANGE[0]}&to={DAY_RANGE[1]}")
    return [datetime.fromisoformat(item["starts_at"]) for item in response.json()["slots"]]


def _fhir_slots(clinic: object, token: str) -> dict[datetime, str]:
    type_id = clinic.appointment_type.pk  # type: ignore[attr-defined]
    statuses = "&status=free&status=busy-unavailable"
    path = (
        f"/fhir/Slot?service-type={type_id}&start=ge{DAY_RANGE[0]}&start=lt{DAY_RANGE[1]}{statuses}"
    )
    entries = get(path, token).json().get("entry", [])
    return {
        datetime.fromisoformat(item["resource"]["start"]): item["resource"]["status"]
        for item in entries
    }


def returns_the_slots_back_when_a_clinician_adds_then_removes_time_off_through_fhir() -> None:
    clinic = make_clinic(rule_fields=HOURS)
    profile = clinic.clinician
    token = token_of(profile.user)
    role_path = f"/fhir/PractitionerRole/{profile.pk}"
    body = stored_role(token, profile)
    body["notAvailable"] = [period(FIRST + HALF_HOUR, FIRST + 3 * HALF_HOUR, "Dentist")]

    added = send("put", role_path, body, token)

    read = stored_role(token, profile)
    row = TimeOff.objects.get(clinician=profile)
    entry = read["notAvailable"][0]  # type: ignore[index]
    assert added.status_code == 200
    assert entry["id"] == str(row.pk)
    assert entry["description"] == "Dentist"
    assert "period" not in entry
    assert entry["during"] == {
        "start": "2030-01-07T10:30:00.000Z",
        "end": "2030-01-07T11:30:00.000Z",
    }
    assert _api_starts(clinic) == [ALL_FOUR[0], ALL_FOUR[3]]
    gone = dict(_fhir_slots(clinic, token))
    assert gone == {
        ALL_FOUR[0]: "free",
        ALL_FOUR[1]: "busy-unavailable",
        ALL_FOUR[2]: "busy-unavailable",
        ALL_FOUR[3]: "free",
    }

    read["notAvailable"] = []
    removed = send("put", role_path, read, token)

    assert removed.status_code == 200
    assert not TimeOff.objects.filter(clinician=profile).exists()
    assert _api_starts(clinic) == ALL_FOUR
    assert set(_fhir_slots(clinic, token).values()) == {"free"}


def returns_200_and_records_time_off_when_the_standard_request_with_during_is_put() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    body = stored_role(token, clinic.clinician)
    body["notAvailable"] = [
        {
            "description": "Dentist",
            "during": {"start": "2030-02-01T09:00:00Z", "end": "2030-02-01T17:00:00Z"},
        }
    ]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, token)

    assert response.status_code == 200
    assert TimeOff.objects.get(clinician=clinic.clinician).reason == "Dentist"


def returns_400_naming_period_when_a_body_still_sends_period() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    body = stored_role(token, clinic.clinician)
    body["notAvailable"] = [
        {"period": {"start": "2030-02-01T09:00:00Z", "end": "2030-02-01T17:00:00Z"}}
    ]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable.period"]
    assert TimeOff.objects.count() == 0


def returns_400_when_an_identical_period_is_added_twice() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    body = stored_role(token, clinic.clinician)
    same = period(FIRST, FIRST + HALF_HOUR, "Dentist")
    body["notAvailable"] = [same, same]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable"]
    assert TimeOff.objects.count() == 0


def returns_400_when_an_identical_period_is_added_to_a_stored_one() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    first = stored_role(token, clinic.clinician)
    first["notAvailable"] = [period(FIRST, FIRST + HALF_HOUR)]
    send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", first, token)
    again = stored_role(token, clinic.clinician)
    again["notAvailable"] = [*again["notAvailable"], period(FIRST, FIRST + HALF_HOUR)]  # type: ignore[misc]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", again, token)

    assert response.status_code == 400
    assert TimeOff.objects.filter(clinician=clinic.clinician).count() == 1


def returns_400_when_the_end_is_before_the_start() -> None:
    clinic = make_clinic()
    token = token_of(clinic.clinician.user)
    body = stored_role(token, clinic.clinician)
    body["notAvailable"] = [period(FIRST + HALF_HOUR, FIRST)]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, token)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable"]
    assert TimeOff.objects.count() == 0


def returns_403_when_another_clinician_puts_time_off_on_the_role() -> None:
    clinic = make_clinic()
    body = stored_role(token_of(clinic.clinician.user), clinic.clinician)
    body["notAvailable"] = [period(FIRST, FIRST + HALF_HOUR)]
    stranger = token_of(make_user(role="CLINICIAN"))

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, stranger)

    assert response.status_code == 403
    assert TimeOff.objects.count() == 0


def returns_400_naming_not_available_when_an_admin_adds_time_off() -> None:
    clinic = make_clinic()
    admin = token_of(role="ADMIN")
    body = stored_role(admin, clinic.clinician)
    body["notAvailable"] = [period(FIRST, FIRST + HALF_HOUR)]

    response = send("put", f"/fhir/PractitionerRole/{clinic.clinician.pk}", body, admin)

    assert response.status_code == 400
    assert element_names(response.json()) == ["PractitionerRole.notAvailable"]
    assert TimeOff.objects.count() == 0
