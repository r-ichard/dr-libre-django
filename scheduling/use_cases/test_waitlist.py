"""Section 5.8: joining, the manual offer and accepting an offer, through the use cases."""

from collections.abc import Iterator
from datetime import timedelta

import pytest

from scheduling.domain.failure import Failure, Success
from scheduling.domain.request_context import RequestContext
from scheduling.models import Appointment, AuditLogEntry, Notification, User, WaitlistEntry
from scheduling.models.builders import add_clinician, make, make_clinic
from scheduling.use_cases.request_context import bind_request_context
from scheduling.use_cases.test_waitlist_support import (
    FOREIGN_REASON,
    NOW,
    ONE_DAY,
    SLOT,
    _admin_user,
    _booked_slot,
    _cancelled_slot,
    _entry_for,
    _offered_entry,
)
from scheduling.use_cases.waitlist import (
    JoinCommand,
    accept_offer,
    join_waitlist,
    offer_waitlist_entry,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def request_context() -> Iterator[None]:
    with bind_request_context(RequestContext("corr-waitlist", NOW)):
        yield


def _join_command(clinic_type_id: object, **overrides: object) -> JoinCommand:
    fields: dict[str, object] = {
        "appointment_type_id": clinic_type_id,
        "earliest_at": SLOT - ONE_DAY,
        "latest_at": SLOT + ONE_DAY,
        "preferred_clinician_id": None,
        "patient_id": None,
    }
    return JoinCommand(**{**fields, **overrides})  # type: ignore[arg-type]


def _entry_of(result: Success[WaitlistEntry] | Failure) -> WaitlistEntry:
    assert isinstance(result, Success), result
    return result.value


# --- join ---


def returns_waiting_entry_for_self_when_patient_joins() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk)

    entry = _entry_of(join_waitlist(command, clinic.patient))

    assert entry.status == "WAITING"
    assert entry.patient_id == clinic.patient.pk
    assert entry.appointment_type_id == clinic.appointment_type.pk
    assert entry.preferred_clinician_id is None
    assert (entry.earliest_at, entry.latest_at) == (SLOT - ONE_DAY, SLOT + ONE_DAY)
    assert entry.offered_appointment_id is None


def returns_entry_for_named_patient_when_admin_joins() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk, patient_id=clinic.patient.pk)

    entry = _entry_of(join_waitlist(command, _admin_user()))

    assert entry.patient_id == clinic.patient.pk


def returns_forbidden_when_clinician_joins() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk, patient_id=clinic.patient.pk)

    assert join_waitlist(command, clinic.clinician.user) == Failure.forbidden()
    assert WaitlistEntry.objects.count() == 0


def returns_forbidden_when_patient_names_another_patient() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk, patient_id=make("User").pk)

    assert join_waitlist(command, clinic.patient) == Failure.forbidden()


def returns_not_found_when_type_inactive() -> None:
    clinic = make_clinic(type_fields={"is_active": False})

    result = join_waitlist(_join_command(clinic.appointment_type.pk), clinic.patient)

    assert result == Failure.not_found()
    assert WaitlistEntry.objects.count() == 0


def returns_not_found_when_preferred_clinician_inactive() -> None:
    clinic = make_clinic()
    gone = add_clinician(clinic.department, user=make("User", role="CLINICIAN", is_active=False))
    command = _join_command(clinic.appointment_type.pk, preferred_clinician_id=gone.pk)

    assert join_waitlist(command, clinic.patient) == Failure.not_found()


def returns_not_found_when_preferred_clinician_in_other_department() -> None:
    clinic = make_clinic()
    stranger = add_clinician(make("Department"))
    command = _join_command(clinic.appointment_type.pk, preferred_clinician_id=stranger.pk)

    assert join_waitlist(command, clinic.patient) == Failure.not_found()


def returns_entry_with_preferred_clinician_when_active_clinician_named() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk, preferred_clinician_id=clinic.clinician.pk)

    entry = _entry_of(join_waitlist(command, clinic.patient))

    assert entry.preferred_clinician_id == clinic.clinician.pk


def returns_not_found_when_patient_inactive() -> None:
    clinic = make_clinic()
    inactive = make("User", is_active=False)
    command = _join_command(clinic.appointment_type.pk, patient_id=inactive.pk)

    assert join_waitlist(command, _admin_user()) == Failure.not_found()


def returns_invalid_input_when_window_ends_before_it_starts() -> None:
    clinic = make_clinic()
    command = _join_command(clinic.appointment_type.pk, earliest_at=SLOT, latest_at=SLOT)

    result = join_waitlist(command, clinic.patient)

    assert isinstance(result, Failure)
    assert result.code == "invalid_input"


def returns_invalid_input_when_latest_time_already_passed() -> None:
    clinic = make_clinic()
    command = _join_command(
        clinic.appointment_type.pk, earliest_at=NOW - ONE_DAY, latest_at=NOW - timedelta(hours=1)
    )

    result = join_waitlist(command, clinic.patient)

    assert isinstance(result, Failure)
    assert result.code == "invalid_input"


def returns_audit_entry_without_free_text_when_joined() -> None:
    clinic = make_clinic()

    entry = _entry_of(join_waitlist(_join_command(clinic.appointment_type.pk), clinic.patient))

    audit = AuditLogEntry.objects.get(action="waitlist.join")
    assert audit.entity_type == "WaitlistEntry"
    assert audit.entity_id == str(entry.pk)
    assert audit.actor_id == clinic.patient.pk
    assert audit.metadata["ids"]["patient_id"] == str(clinic.patient.pk)
    assert audit.metadata["statuses"] == {"waitlist_status": "WAITING"}


def returns_no_notification_when_joined() -> None:
    clinic = make_clinic()

    join_waitlist(_join_command(clinic.appointment_type.pk), clinic.patient)

    assert Notification.objects.count() == 0


# --- manual offer ---


def returns_offered_when_slot_free() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    offered = _entry_of(offer_waitlist_entry(entry.pk, _admin_user()))

    entry.refresh_from_db()
    assert offered.status == "OFFERED"
    assert entry.status == "OFFERED"
    assert entry.offered_appointment_id == freed.pk
    assert entry.version == 2


def returns_audit_and_notification_when_manual_offer_made() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)
    admin = _admin_user()

    offer_waitlist_entry(entry.pk, admin)

    audit = AuditLogEntry.objects.get(action="waitlist.offer")
    assert audit.actor_id == admin.pk
    assert audit.metadata["statuses"] == {"waitlist_status": "OFFERED"}
    notification = Notification.objects.get(kind="WAITLIST_OFFERED")
    assert notification.recipient_id == clinic.patient.pk
    assert notification.waitlist_entry_id == entry.pk
    assert notification.appointment_id is None
    assert notification.email_pending is True


def returns_no_clinician_available_when_clinician_booked() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    _booked_slot(clinic)
    entry = _entry_for(clinic)

    assert offer_waitlist_entry(entry.pk, _admin_user()) == Failure.no_clinician_available()
    entry.refresh_from_db()
    assert entry.status == "WAITING"


def returns_no_clinician_available_when_no_cancelled_slot_in_window() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic, SLOT + timedelta(days=7))
    entry = _entry_for(clinic)

    assert offer_waitlist_entry(entry.pk, _admin_user()) == Failure.no_clinician_available()


def returns_invalid_transition_when_manual_offer_for_entry_not_waiting() -> None:
    clinic = make_clinic()
    freed = _cancelled_slot(clinic)
    entry = _offered_entry(clinic, freed)

    result = offer_waitlist_entry(entry.pk, _admin_user())

    assert result == Failure.invalid_transition("OFFERED")


def returns_forbidden_when_patient_offers() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    assert offer_waitlist_entry(entry.pk, clinic.patient) == Failure.forbidden()


def returns_not_found_when_offering_unknown_entry() -> None:
    assert offer_waitlist_entry(make("User").pk, _admin_user()) == Failure.not_found()


def returns_next_slot_when_first_cancelled_slot_is_held_by_another_entry() -> None:
    clinic = make_clinic()
    held = _cancelled_slot(clinic)
    free = _cancelled_slot(clinic, SLOT + timedelta(hours=1))
    _offered_entry(clinic, held, patient=make("User"))
    entry = _entry_for(clinic)

    offer_waitlist_entry(entry.pk, _admin_user())

    entry.refresh_from_db()
    assert entry.offered_appointment_id == free.pk


def returns_slot_of_preferred_clinician_when_manual_offer_for_named_clinician() -> None:
    clinic = make_clinic()
    other = add_clinician(clinic.department)
    _cancelled_slot(clinic, clinician=other)
    wanted = _cancelled_slot(clinic, SLOT + timedelta(hours=1))
    entry = _entry_for(clinic, preferred_clinician=clinic.clinician)

    offer_waitlist_entry(entry.pk, _admin_user())

    entry.refresh_from_db()
    assert entry.offered_appointment_id == wanted.pk


# --- accept ---


def returns_booked_when_patient_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    result = accept_offer(entry.pk, clinic.patient)

    entry.refresh_from_db()
    assert _entry_of(result).status == "BOOKED"
    assert entry.status == "BOOKED"
    placed = Appointment.objects.get(waitlist_entry=entry)
    assert placed.status == "BOOKED"
    assert placed.patient_id == clinic.patient.pk
    assert placed.clinician_id == clinic.clinician.pk
    assert placed.appointment_type_id == clinic.appointment_type.pk
    assert placed.starts_at == SLOT


def returns_inherited_version_of_entry_when_accepted() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    accept_offer(entry.pk, clinic.patient)

    entry.refresh_from_db()
    placed = Appointment.objects.get(waitlist_entry=entry)
    assert placed.inherited_version == entry.version
    assert entry.version == 2


def returns_booked_when_admin_accepts_for_patient() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    result = accept_offer(entry.pk, _admin_user())

    assert _entry_of(result).status == "BOOKED"
    assert Appointment.objects.get(waitlist_entry=entry).patient_id == clinic.patient.pk


def returns_forbidden_when_other_patient_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    stranger = make("User")
    assert isinstance(stranger, User)

    result = accept_offer(entry.pk, stranger)

    assert result == Failure.forbidden()
    entry.refresh_from_db()
    assert entry.status == "OFFERED"


def returns_forbidden_when_offered_clinician_accepts() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    result = accept_offer(entry.pk, clinic.clinician.user)

    assert result == Failure.forbidden()
    entry.refresh_from_db()
    assert entry.status == "OFFERED"


def returns_conflict_and_keeps_offer_when_slot_taken() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    _booked_slot(clinic)

    result = accept_offer(entry.pk, clinic.patient)

    assert result == Failure.conflict(["clinician"])
    entry.refresh_from_db()
    assert entry.status == "OFFERED"
    assert entry.version == 1
    assert not Appointment.objects.filter(waitlist_entry__isnull=False).exists()


def returns_rule_violation_when_lead_time_short() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    with bind_request_context(RequestContext("corr-late", SLOT - timedelta(hours=1))):
        result = accept_offer(entry.pk, clinic.patient)

    assert result == Failure.rule_violation(["lead_time_too_short"])
    entry.refresh_from_db()
    assert entry.status == "OFFERED"


def returns_invalid_transition_when_accepting_entry_not_offered() -> None:
    clinic = make_clinic()
    entry = _entry_for(clinic)

    assert accept_offer(entry.pk, clinic.patient) == Failure.invalid_transition("WAITING")


def returns_invalid_transition_when_accepting_twice() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))
    accept_offer(entry.pk, clinic.patient)

    assert accept_offer(entry.pk, clinic.patient) == Failure.invalid_transition("BOOKED")
    assert Appointment.objects.filter(waitlist_entry=entry).count() == 1


def returns_audit_and_booked_notification_when_accepted() -> None:
    clinic = make_clinic()
    entry = _offered_entry(clinic, _cancelled_slot(clinic))

    accept_offer(entry.pk, clinic.patient)

    audit = AuditLogEntry.objects.get(action="waitlist.accept")
    assert audit.actor_id == clinic.patient.pk
    assert audit.metadata["statuses"] == {"waitlist_status": "BOOKED"}
    placed = Appointment.objects.get(waitlist_entry=entry)
    notification = Notification.objects.get(kind="WAITLIST_BOOKED")
    assert notification.recipient_id == clinic.patient.pk
    assert notification.waitlist_entry_id == entry.pk
    assert notification.appointment_id == placed.pk
    assert notification.email_pending is True


def returns_no_foreign_reason_when_offer_shown() -> None:
    clinic = make_clinic()
    _cancelled_slot(clinic)
    entry = _entry_for(clinic)

    offer_waitlist_entry(entry.pk, _admin_user())

    notification = Notification.objects.get(kind="WAITLIST_OFFERED")
    assert FOREIGN_REASON not in f"{notification.title} {notification.body}"
    assert FOREIGN_REASON not in str(AuditLogEntry.objects.get(action="waitlist.offer").metadata)
