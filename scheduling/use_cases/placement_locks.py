"""Section 5.2 step 2: the row locks of a placement, in the global order: clinicians by id,
patient, rooms by id."""

from uuid import UUID

from scheduling.domain.vocabulary import Role
from scheduling.models import AppointmentType, ClinicianProfile, Room, User
from scheduling.use_cases.schedule_loading import department_clinicians


def lock_clinicians(
    appointment_type: AppointmentType, clinician_id: UUID | None, online_only: bool
) -> list[ClinicianProfile]:
    candidates = department_clinicians(appointment_type, clinician_id, online_only)
    # of=self: the user rows stay unlocked, or the lock order would no longer be ours.
    locked = candidates.select_for_update(of=("self",), no_key=True).order_by("pk")
    return list(locked)


def lock_patient(patient_id: UUID) -> User | None:
    patients = User.objects.select_for_update(no_key=True)
    return patients.filter(pk=patient_id, is_active=True, role=Role.PATIENT).first()


def lock_rooms(appointment_type: AppointmentType, room_id: UUID | None) -> list[Room] | None:
    """None when the named room is not an active room of the department; an empty list when the
    type needs no room."""
    active = Room.objects.filter(department_id=appointment_type.department_id, is_active=True)
    if room_id is not None:
        active = active.filter(pk=room_id)
    elif not appointment_type.needs_room:
        return []
    rooms = list(active.select_for_update(no_key=True).order_by("pk"))
    return None if room_id is not None and not rooms else rooms
