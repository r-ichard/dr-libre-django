"""Section 10: the names an admin notice sentence needs, read by id. A subject that is gone gives
None, so the views layer picks the generic noun."""

from uuid import UUID

from scheduling.models import Appointment, User, WaitlistEntry


def patient_name_of_appointment(subject: UUID) -> str | None:
    row = Appointment.objects.select_related("patient").filter(pk=subject).first()
    return row.patient.full_name if row else None


def patient_name_of_waitlist_entry(subject: UUID) -> str | None:
    row = WaitlistEntry.objects.select_related("patient").filter(pk=subject).first()
    return row.patient.full_name if row else None


def user_name(subject: UUID) -> str | None:
    row = User.objects.filter(pk=subject).first()
    return row.full_name if row else None
