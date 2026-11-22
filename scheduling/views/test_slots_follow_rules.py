"""Section 9.3: a new rule's slots appear in GET /api/v1/slots, a deleted rule's disappear."""

from datetime import UTC, datetime, time

import pytest

from scheduling.domain.request_context import RequestContext
from scheduling.models import AvailabilityRule, User
from scheduling.models.builders import Clinic, make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views import clock
from scheduling.views.api_clients import browser_api_client

pytestmark = pytest.mark.django_db

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
TUESDAY = "from=2030-01-08T00:00:00Z&to=2030-01-09T00:00:00Z"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now_utc", lambda: NOW)


def _starts(clinic: Clinic) -> list[str]:
    ids = f"appointment_type_id={clinic.appointment_type.pk}&clinician_id={clinic.clinician.pk}"
    query = f"{ids}&{TUESDAY}"
    return [
        slot["starts_at"]
        for slot in browser_api_client().get(f"/api/v1/slots?{query}").json()["slots"]
    ]


def _actor(clinic: Clinic) -> User:
    user = clinic.clinician.user
    assert isinstance(user, User)
    return user


def returns_offers_new_rule_slots_when_rule_created() -> None:
    from scheduling.use_cases.availability import RuleCommand, create_rule

    clinic = make_clinic()
    assert _starts(clinic) == []

    with bind_request_context(RequestContext("corr-slots", NOW)):
        create_rule(RuleCommand(2, time(11, 0), time(12, 0), 30, None), _actor(clinic))

    assert _starts(clinic) == ["2030-01-08T10:00:00Z", "2030-01-08T10:30:00Z"]


def returns_withdraws_slots_when_rule_deleted() -> None:
    from scheduling.use_cases.availability import delete_rule

    clinic = make_clinic(
        rule_fields={
            "weekday": 2,
            "start_time": time(11, 0),
            "end_time": time(12, 0),
            "slot_step_minutes": 30,
        }
    )
    assert len(_starts(clinic)) == 2

    with bind_request_context(RequestContext("corr-slots", NOW)):
        delete_rule(AvailabilityRule.objects.get(clinician=clinic.clinician).pk, _actor(clinic))

    assert _starts(clinic) == []
