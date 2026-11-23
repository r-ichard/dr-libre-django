"""A patient's own appointments, upcoming and past, and the record rule on one of them."""

from datetime import datetime
from uuid import UUID

from django.db.models import Q, QuerySet

from scheduling.domain.failure import Result
from scheduling.domain.portal_options import UPCOMING_STATUSES
from scheduling.models import Appointment, User
from scheduling.use_cases.appointment_list import AppointmentPage
from scheduling.use_cases.record_access import guard_record


def upcoming_appointments(patient: User, now: datetime) -> list[Appointment]:
    return list(_own(patient).filter(_is_upcoming(now)).order_by("starts_at", "pk"))


def past_appointments(patient: User, now: datetime, page: int, page_size: int) -> AppointmentPage:
    matching = _own(patient).exclude(_is_upcoming(now)).order_by("-starts_at", "pk")
    offset = (page - 1) * page_size
    return AppointmentPage(matching.count(), list(matching[offset : offset + page_size]))


def own_appointment(appointment_id: UUID, patient: User) -> Result[Appointment]:
    appointment = _with_details().filter(pk=appointment_id).first()
    return guard_record(appointment, lambda found: found.patient_id == patient.pk)


def _own(patient: User) -> QuerySet[Appointment]:
    return _with_details().filter(patient=patient)


def _with_details() -> QuerySet[Appointment]:
    return Appointment.objects.select_related(
        "clinician__user",
        "clinician__specialty",
        "appointment_type__department__hospital",
        "room",
    )


def _is_upcoming(now: datetime) -> Q:
    return Q(status__in=UPCOMING_STATUSES, starts_at__gt=now)
