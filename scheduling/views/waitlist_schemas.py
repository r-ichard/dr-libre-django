"""Section 14 schemas of the waitlist: a strict join request, and an entry shown with the offered
slot's time, provider and hospital only. The freed appointment's id, patient and reason stay out."""

from collections.abc import Mapping

from rest_framework import serializers

from scheduling.models import WaitlistEntry
from scheduling.use_cases.waitlist import JoinCommand
from scheduling.views.booking_schemas import (
    OffsetDateTimeField,
    format_instant,
    required_instant,
    required_uuid,
    uuid_of,
)
from scheduling.views.schemas import StrictSerializer


class JoinRequest(StrictSerializer):
    appointment_type_id = serializers.UUIDField()
    earliest_at = OffsetDateTimeField()
    latest_at = OffsetDateTimeField()
    preferred_clinician_id = serializers.UUIDField(required=False, allow_null=True)
    patient_id = serializers.UUIDField(required=False)


def join_command_of(values: Mapping[str, object]) -> JoinCommand:
    return JoinCommand(
        appointment_type_id=required_uuid(values, "appointment_type_id"),
        earliest_at=required_instant(values, "earliest_at"),
        latest_at=required_instant(values, "latest_at"),
        preferred_clinician_id=uuid_of(values, "preferred_clinician_id"),
        patient_id=uuid_of(values, "patient_id"),
    )


def waitlist_entry_body(entry: WaitlistEntry) -> dict[str, object]:
    preferred_id = entry.preferred_clinician_id
    return {
        "id": str(entry.pk),
        "status": entry.status,
        "appointment_type_id": str(entry.appointment_type_id),
        "preferred_clinician_id": str(preferred_id) if preferred_id is not None else None,
        "earliest_at": format_instant(entry.earliest_at),
        "latest_at": format_instant(entry.latest_at),
        "offer": _offer_body(entry),
    }


def _offer_body(entry: WaitlistEntry) -> dict[str, object] | None:
    offered = entry.offered_appointment
    if entry.status != "OFFERED" or offered is None:
        return None
    hospital = entry.appointment_type.department.hospital
    return {
        "starts_at": format_instant(offered.starts_at),
        "ends_at": format_instant(offered.ends_at),
        "time_zone": hospital.time_zone,
        "provider_name": offered.clinician.user.full_name,
        "hospital_name": hospital.name,
    }
