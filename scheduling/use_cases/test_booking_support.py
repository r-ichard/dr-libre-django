"""Shared builders of the booking tests (task 12). The new modules are imported inside the
helpers, so a missing one fails the test that needs it and not the whole collection."""

from __future__ import annotations

import re
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta

from django.apps import apps
from django.core import mail
from django.db.models import Model

from scheduling.domain.failure import Result, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import BookingHold, User
from scheduling.models.builders import STARTS_AT, Clinic
from scheduling.use_cases.request_context import bind_request_context

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
SLOT = STARTS_AT
THIRTY_MINUTES = timedelta(minutes=30)
TEN_MINUTES = timedelta(minutes=10)
ADDRESS = "203.0.113.7"
VISITOR_EMAIL = "visitor.one@example.test"
VISITOR_NAME = "Vera Visitor"
VISITOR_BIRTH_DATE = date(1985, 3, 14)
VISITOR_PHONE = "+49 30 777"
CODE_PATTERN = re.compile(r"\b(\d{6})\b")


def _at(instant: datetime) -> AbstractContextManager[None]:
    return bind_request_context(RequestContext("corr-booking", instant))


def _hold_command(clinic: Clinic, **overrides: object) -> object:
    from scheduling.use_cases.booking_holds import HoldCommand

    fields: dict[str, object] = {
        "appointment_type_id": clinic.appointment_type.pk,
        "clinician_id": clinic.clinician.pk,
        "starts_at": SLOT,
        "full_name": VISITOR_NAME,
        "birth_date": VISITOR_BIRTH_DATE,
        "email": VISITOR_EMAIL,
        "phone": VISITOR_PHONE,
        "reason": "",
        "terms_accepted": True,
    }
    return HoldCommand(**{**fields, **overrides})  # type: ignore[arg-type]


def _create(clinic: Clinic, address: str = ADDRESS, **overrides: object) -> Result[BookingHold]:
    from scheduling.use_cases.booking_holds import create_hold

    return create_hold(_hold_command(clinic, **overrides), address)  # type: ignore[arg-type]


def _held(clinic: Clinic, address: str = ADDRESS, **overrides: object) -> BookingHold:
    result = _create(clinic, address, **overrides)
    assert isinstance(result, Success), result
    return result.value


def _resend(hold_id: object, address: str = ADDRESS) -> Result[BookingHold]:
    from scheduling.use_cases.booking_holds import resend_code

    return resend_code(hold_id, address)  # type: ignore[arg-type]


def _verify(hold_id: object, code: str) -> Result[object]:
    from scheduling.use_cases.booking_verification import verify_hold

    return verify_hold(hold_id, code, "pytest-agent")  # type: ignore[arg-type]


def _last_code() -> str:
    """The code as the visitor reads it, from the newest message in the outbox."""
    found = CODE_PATTERN.search(str(mail.outbox[-1].body))
    assert found is not None, mail.outbox[-1].body
    return found.group(1)


def _wrong_code(right: str) -> str:
    return "000000" if right != "000000" else "111111"


def _model_rows(model_name: str) -> list[Model]:
    return list(apps.get_model("scheduling", model_name)._default_manager.all())


def _user_count() -> int:
    return User.objects.count()
