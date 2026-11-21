"""Section 14 schemas for slots and appointments: strict requests, UTC instants with the
hospital time zone beside them in responses."""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from rest_framework import serializers

from scheduling.domain.failure import Failure, FieldMessage
from scheduling.domain.vocabulary import AppointmentStatus
from scheduling.models import Appointment
from scheduling.use_cases.appointment_list import AppointmentFilters
from scheduling.use_cases.free_slots_query import FoundSlots
from scheduling.use_cases.placement import PlacementCommand
from scheduling.views.schemas import StrictSerializer

DEFAULT_PAGE_SIZE = 20
MAXIMUM_PAGE_SIZE = 100
CANCELLATION_REASON_MAXIMUM = 1000
VISIT_REASON_MAXIMUM = 200
MAXIMUM_PAGE = 1_000_000
EARLIEST_INSTANT = datetime(2000, 1, 1, tzinfo=UTC)
LATEST_INSTANT = datetime(2100, 1, 1, tzinfo=UTC)
DATE_OUT_OF_RANGE = "Use a date between the years 2000 and 2099."


class OffsetDateTimeField(serializers.DateTimeField):
    """An instant must say its offset; DRF would otherwise guess the server's zone."""

    def enforce_timezone(self, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise serializers.ValidationError("Include a UTC offset, such as Z.")
        try:
            instant = value.astimezone(UTC)
        except OverflowError:
            raise serializers.ValidationError(DATE_OUT_OF_RANGE) from None
        if not EARLIEST_INSTANT <= instant < LATEST_INSTANT:
            raise serializers.ValidationError(DATE_OUT_OF_RANGE)
        return instant


class SlotsQuery(StrictSerializer):
    appointment_type_id = serializers.UUIDField()
    clinician_id = serializers.UUIDField(required=False)
    # "from" is a Python keyword, so the range fields are added to the class namespace by name.
    locals()["from"] = OffsetDateTimeField()
    locals()["to"] = OffsetDateTimeField()


class AppointmentsQuery(StrictSerializer):
    patient_id = serializers.UUIDField(required=False)
    clinician_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(
        choices=[status.value for status in AppointmentStatus], required=False
    )
    locals()["from"] = OffsetDateTimeField(required=False)
    locals()["to"] = OffsetDateTimeField(required=False)
    page = serializers.IntegerField(min_value=1, max_value=MAXIMUM_PAGE, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=MAXIMUM_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


class BookRequest(StrictSerializer):
    appointment_type_id = serializers.UUIDField()
    starts_at = OffsetDateTimeField()
    clinician_id = serializers.UUIDField(required=False)
    patient_id = serializers.UUIDField(required=False)
    room_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(
        max_length=VISIT_REASON_MAXIMUM, allow_blank=True, required=False
    )


def uuid_of(values: Mapping[str, object], key: str) -> UUID | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, UUID):
        raise TypeError(f"{key} passed its schema, so it is a UUID")
    return value


def instant_of(values: Mapping[str, object], key: str) -> datetime | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"{key} passed its schema, so it is a datetime")
    return value


def required_uuid(values: Mapping[str, object], key: str) -> UUID:
    value = uuid_of(values, key)
    if value is None:
        raise TypeError(f"{key} is required by its schema")
    return value


def required_instant(values: Mapping[str, object], key: str) -> datetime:
    value = instant_of(values, key)
    if value is None:
        raise TypeError(f"{key} is required by its schema")
    return value


def placement_command_of(values: Mapping[str, object]) -> PlacementCommand:
    return PlacementCommand(
        appointment_type_id=required_uuid(values, "appointment_type_id"),
        starts_at=required_instant(values, "starts_at"),
        clinician_id=uuid_of(values, "clinician_id"),
        patient_id=uuid_of(values, "patient_id"),
        room_id=uuid_of(values, "room_id"),
        reason=str(values.get("reason", "")),
    )


def filters_of(values: Mapping[str, object]) -> AppointmentFilters:
    status = values.get("status")
    return AppointmentFilters(
        patient_id=uuid_of(values, "patient_id"),
        clinician_id=uuid_of(values, "clinician_id"),
        status=AppointmentStatus(str(status)) if status is not None else None,
        starts_from=instant_of(values, "from"),
        starts_before=instant_of(values, "to"),
    )


def refuse_empty_range(values: Mapping[str, object]) -> Failure | None:
    starts, ends = instant_of(values, "from"), instant_of(values, "to")
    if starts is None or ends is None or ends > starts:
        return None
    return Failure.invalid_input([FieldMessage("to", "The end must be after the start.")])


def format_instant(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def slots_body(found: FoundSlots) -> dict[str, object]:
    return {
        "time_zone": found.time_zone,
        "slots": [
            {
                "starts_at": format_instant(offer.start),
                "ends_at": format_instant(offer.start + found.duration),
                "clinician_ids": [str(identifier) for identifier in offer.clinician_ids],
            }
            for offer in found.offers
        ],
    }


def appointment_body(appointment: Appointment) -> dict[str, object]:
    """The visit reason is shown: every caller already limits readers to the appointment's patient,
    its clinician and an admin. Clinical notes never leave."""
    room_id = appointment.room_id
    return {
        "id": str(appointment.pk),
        "appointment_type_id": str(appointment.appointment_type_id),
        "clinician_id": str(appointment.clinician_id),
        "patient_id": str(appointment.patient_id),
        "room_id": str(room_id) if room_id is not None else None,
        "starts_at": format_instant(appointment.starts_at),
        "ends_at": format_instant(appointment.ends_at),
        "time_zone": appointment.appointment_type.department.hospital.time_zone,
        "status": appointment.status,
        "source": appointment.source,
        "reason": appointment.patient_reason,
    }


class CancelRequest(StrictSerializer):
    # The limit is ours; the spec names none.
    reason = serializers.CharField(max_length=CANCELLATION_REASON_MAXIMUM)


class RescheduleRequest(StrictSerializer):
    starts_at = OffsetDateTimeField()


class NoFieldsRequest(StrictSerializer):
    pass
