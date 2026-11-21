"""Section 15.3: an accepted waitlist entry and its booking are one FHIR Appointment."""

import pytest
from django.db import IntegrityError, connection, transaction

from scheduling.models.builders import field_of, make, model_class

pytestmark = pytest.mark.django_db


def returns_appointment_linked_to_entry_when_waitlist_entry_is_set() -> None:
    entry = make("WaitlistEntry")

    booked = make("Appointment", waitlist_entry=entry)

    stored = model_class("Appointment")._default_manager.get(pk=booked.pk)
    assert field_of(stored, "waitlist_entry_id") == entry.pk


def rejects_second_appointment_when_entry_already_booked() -> None:
    entry = make("WaitlistEntry")
    make("Appointment", waitlist_entry=entry)

    with pytest.raises(IntegrityError), transaction.atomic():
        make("Appointment", waitlist_entry=entry)


def rejects_entry_delete_when_appointment_refers_to_it() -> None:
    entry = make("WaitlistEntry")
    make("Appointment", waitlist_entry=entry)

    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM scheduling_waitlistentry WHERE id = %s", [entry.pk])
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def rejects_entry_delete_through_orm_when_appointment_refers_to_it() -> None:
    from django.db.models import ProtectedError

    entry = make("WaitlistEntry")
    make("Appointment", waitlist_entry=entry)

    with pytest.raises(ProtectedError):
        entry.delete()


def rejects_inherited_version_when_appointment_has_no_waitlist_entry() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make("Appointment", inherited_version=3)


def returns_appointment_when_inherited_version_comes_with_waitlist_entry() -> None:
    entry = make("WaitlistEntry")

    booked = make("Appointment", waitlist_entry=entry, inherited_version=3)

    stored = model_class("Appointment")._default_manager.get(pk=booked.pk)
    assert field_of(stored, "inherited_version") == 3


def rejects_negative_inherited_version() -> None:
    entry = make("WaitlistEntry")

    with pytest.raises(IntegrityError), transaction.atomic():
        make("Appointment", waitlist_entry=entry, inherited_version=-1)


def returns_larger_version_when_booked_appointment_replaces_waiting_entry() -> None:
    entry = make("WaitlistEntry")
    entry.save()
    entry.save()
    assert field_of(entry, "version") == 3

    booked = make("Appointment", waitlist_entry=entry, inherited_version=3)

    stored = model_class("Appointment")._default_manager.get(pk=booked.pk)
    resource_version = field_of(stored, "inherited_version") + field_of(stored, "version")  # type: ignore[operator]
    assert resource_version == 4


def returns_zero_inherited_version_when_appointment_is_booked_directly() -> None:
    booked = make("Appointment")

    stored = model_class("Appointment")._default_manager.get(pk=booked.pk)
    assert field_of(stored, "inherited_version") == 0


def returns_notification_about_waitlist_entry_when_offer_is_sent() -> None:
    entry = make("WaitlistEntry")

    note = make("Notification", kind="WAITLIST_OFFERED", waitlist_entry=entry)

    stored = model_class("Notification")._default_manager.get(pk=note.pk)
    assert field_of(stored, "waitlist_entry_id") == entry.pk


def rejects_entry_delete_when_notification_refers_to_it() -> None:
    entry = make("WaitlistEntry")
    make("Notification", kind="WAITLIST_OFFERED", waitlist_entry=entry)

    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM scheduling_waitlistentry WHERE id = %s", [entry.pk])
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
