"""Task 20, item 14: a refused delete of a user changes nothing, even the clean-up before it."""

from collections.abc import Callable
from uuid import UUID

import pytest
from pytest import MonkeyPatch

from scheduling.domain.failure import Failure
from scheduling.models import Appointment, AuditLogEntry, Notification, Session, SignInLink, User
from scheduling.models.builders import make
from scheduling.use_cases import admin_users
from scheduling.use_cases.admin_users import delete_user
from scheduling.use_cases.test_admin_record_support import _an_admin, _in_context

pytestmark = pytest.mark.django_db


def _insert_appointment_after_first_answer(
    monkeypatch: MonkeyPatch, patient: User
) -> Callable[[], int]:
    real_dependents = admin_users.user_dependents
    answers: list[int] = []

    def answer_then_insert(user_id: UUID, actor_id: UUID) -> list[str]:
        found = real_dependents(user_id, actor_id)
        if not answers:
            make("Appointment", patient=patient)
        answers.append(1)
        return found

    monkeypatch.setattr(admin_users, "user_dependents", answer_then_insert)
    return lambda: len(answers)


def returns_has_dependents_and_keeps_clean_up_rows_when_a_dependent_appears_before_the_delete(
    monkeypatch: MonkeyPatch,
) -> None:
    patient = make("User", role="PATIENT")
    assert isinstance(patient, User)
    make("Session", user=patient)
    make("SignInLink", patient=patient)
    make("Notification", recipient=patient)
    admin = _an_admin()
    _insert_appointment_after_first_answer(monkeypatch, patient)

    result = _in_context(lambda: delete_user(patient.pk, admin))

    assert result == Failure.has_dependents(["1 appointment as a patient"])
    assert User.objects.filter(pk=patient.pk).exists()
    assert Session.objects.filter(user=patient).count() == 1
    assert SignInLink.objects.filter(patient=patient).count() == 1
    assert Notification.objects.filter(recipient=patient).count() == 1
    assert Appointment.objects.filter(patient=patient).count() == 1
    assert not AuditLogEntry.objects.filter(action="user.delete").exists()
