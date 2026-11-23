"""A patient's own waitlist entries and the record rule on one of them."""

from uuid import UUID

from django.db.models import QuerySet

from scheduling.domain.failure import Result
from scheduling.models import AppointmentType, ClinicianProfile, User, WaitlistEntry
from scheduling.use_cases.record_access import guard_record


def own_waitlist(patient: User) -> list[WaitlistEntry]:
    return list(with_details().filter(patient=patient).order_by("-created_at", "-pk"))


def own_entry(entry_id: UUID, patient: User) -> Result[WaitlistEntry]:
    entry = with_details().filter(pk=entry_id).first()
    return guard_record(entry, lambda found: found.patient_id == patient.pk)


def with_details() -> QuerySet[WaitlistEntry]:
    return WaitlistEntry.objects.select_related(
        "appointment_type__department__hospital",
        "preferred_clinician__user",
        "offered_appointment__clinician__user",
        "offered_appointment__clinician__specialty",
    )


def joinable_types() -> list[AppointmentType]:
    """Active types of active hospitals, the services a patient can wait for."""
    types = AppointmentType.objects.filter(is_active=True, department__hospital__is_active=True)
    return list(
        types.select_related("department__hospital").order_by(
            "department__hospital__name", "department__name", "name"
        )
    )


def joinable_providers(types: list[AppointmentType]) -> list[ClinicianProfile]:
    departments = {appointment_type.department_id for appointment_type in types}
    clinicians = ClinicianProfile.objects.filter(
        department_id__in=departments, user__is_active=True
    )
    return list(clinicians.select_related("user", "specialty").order_by("user__full_name"))
