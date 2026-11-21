"""Section 7.1 and 7.6: a mail server that is down fails a hold or a resend with a failure of its
own and leaves nothing behind."""

from collections.abc import Iterator

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.models import BookingHold, RateLimitHit, User
from scheduling.models.access import VerificationCode
from scheduling.models.builders import make_clinic
from scheduling.use_cases.test_booking_support import (
    NOW,
    VISITOR_EMAIL,
    _at,
    _create,
    _held,
    _resend,
)
from scheduling.use_cases.test_sign_in_link_support import MailServerDownBackend

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with _at(NOW):
        yield


def _mail_server_goes_down(settings: object) -> None:
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {
            "BACKEND": f"{MailServerDownBackend.__module__}.MailServerDownBackend",
            "OPTIONS": {},
        }
    }


def returns_mail_unavailable_and_holds_nothing_when_hold_cannot_send(settings: object) -> None:
    clinic = make_clinic()
    users_before = User.objects.count()
    _mail_server_goes_down(settings)

    result = _create(clinic)

    assert result == Failure.mail_unavailable()
    assert BookingHold.objects.count() == 0
    assert VerificationCode.objects.count() == 0
    assert RateLimitHit.objects.count() == 0
    assert User.objects.count() == users_before


def returns_earlier_hold_kept_when_replacing_hold_cannot_send(settings: object) -> None:
    clinic = make_clinic()
    earlier = _held(clinic)
    _mail_server_goes_down(settings)

    result = _create(clinic)

    assert isinstance(result, Failure)
    assert list(BookingHold.objects.values_list("pk", flat=True)) == [earlier.pk]


def returns_mail_unavailable_and_old_code_kept_when_resend_cannot_send(settings: object) -> None:
    hold = _held(make_clinic())
    old_hash = VerificationCode.objects.get().code_hash
    hits_before = RateLimitHit.objects.count()
    _mail_server_goes_down(settings)

    result = _resend(hold.pk)

    assert result == Failure.mail_unavailable()
    assert VerificationCode.objects.get().code_hash == old_hash
    assert RateLimitHit.objects.count() == hits_before


def returns_success_when_mail_server_is_up_again(settings: object) -> None:
    clinic = make_clinic()
    _mail_server_goes_down(settings)
    assert isinstance(_create(clinic), Failure)
    settings.MAILERS = {  # type: ignore[attr-defined]
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend", "OPTIONS": {}}
    }

    assert isinstance(_create(clinic), Success)
    assert BookingHold.objects.get().visitor_email == VISITOR_EMAIL
