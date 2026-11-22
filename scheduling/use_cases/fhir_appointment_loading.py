"""Task 23a, spec 15.3: rows of the three origins as `Appointment` resources, a fixed number of
queries for a page. The clinical note is read only for the rows whose clinician is the viewer."""

from uuid import UUID

from django.db.models import Q

from scheduling.domain.fhir_appointment import (
    BookingFacts,
    HoldFacts,
    ServiceFacts,
    WaitlistFacts,
    booking_resource,
    hold_resource,
    waitlist_resource,
)
from scheduling.domain.fhir_common import Resource
from scheduling.models import Appointment, AppointmentType, BookingHold, ClinicalNote, WaitlistEntry


def booked(logical_ids: list[UUID], viewer_id: UUID) -> list[Resource]:
    rows = list(
        Appointment.objects.filter(Q(waitlist_entry_id__in=logical_ids) | Q(pk__in=logical_ids))
        .select_related("appointment_type", "clinician")
        .order_by("pk")
    )
    own = [row.pk for row in rows if row.clinician.user_id == viewer_id]
    notes = dict(
        ClinicalNote.objects.filter(appointment_id__in=own).values_list(
            "appointment_id", "clinical_notes"
        )
    )
    return [booking_resource(_booking_facts(row, notes.get(row.pk))) for row in rows]


def waiting(entry_ids: list[UUID]) -> list[Resource]:
    rows = WaitlistEntry.objects.filter(pk__in=entry_ids).select_related(
        "appointment_type", "preferred_clinician", "offered_appointment__clinician"
    )
    return [waitlist_resource(_waitlist_facts(row)) for row in rows]


def holds(hold_ids: list[UUID]) -> list[Resource]:
    rows = BookingHold.objects.filter(pk__in=hold_ids).select_related(
        "appointment_type", "clinician"
    )
    return [
        hold_resource(
            HoldFacts(
                row.pk,
                row.version,
                row.updated_at,
                row.source,
                row.starts_at,
                row.ends_at,
                _service(row.appointment_type),
                row.clinician.user_id,
            )
        )
        for row in rows
    ]


def _service(appointment_type: AppointmentType) -> ServiceFacts:
    return ServiceFacts(appointment_type.pk, appointment_type.name)


def _booking_facts(row: Appointment, comment: str | None) -> BookingFacts:
    return BookingFacts(
        row.waitlist_entry_id or row.pk,
        row.inherited_version + row.version,
        row.updated_at,
        row.status,
        row.source,
        row.starts_at,
        row.ends_at,
        _service(row.appointment_type),
        row.patient_id,
        row.clinician.user_id,
        row.room_id,
        row.patient_reason,
        row.cancellation_reason,
        comment,
    )


def _waitlist_facts(row: WaitlistEntry) -> WaitlistFacts:
    offer = row.offered_appointment
    preferred = row.preferred_clinician
    return WaitlistFacts(
        row.pk,
        row.version,
        row.updated_at,
        row.status,
        _service(row.appointment_type),
        row.patient_id,
        row.earliest_at,
        row.latest_at,
        preferred.user_id if preferred else None,
        offer.starts_at if offer else None,
        offer.ends_at if offer else None,
        offer.clinician.user_id if offer else None,
    )
