"""Section 9.3: the day timeline of the active rooms of the clinician's department. A patient's
name is read only for the clinician's own appointments; any other row carries no patient at all."""

from dataclasses import dataclass
from datetime import date, datetime

from scheduling.domain.appointment_status import ACTIVE_STATUSES
from scheduling.domain.room_timeline import occupancy_label
from scheduling.domain.workspace_day import local_day_bounds
from scheduling.models import Appointment, ClinicianProfile, Room
from scheduling.use_cases.clinician_availability import bookable_rooms


@dataclass(frozen=True)
class RoomCell:
    starts_at: datetime
    ends_at: datetime
    label: str
    appointment_id: object | None


@dataclass(frozen=True)
class RoomDay:
    room: Room
    cells: list[RoomCell]


def room_day(profile: ClinicianProfile, day: date) -> list[RoomDay]:
    rooms = bookable_rooms(profile)
    start, end = local_day_bounds(day, profile.department.hospital.time_zone)
    rows = Appointment.objects.select_related("patient").filter(
        room__in=rooms,
        status__in=ACTIVE_STATUSES,
        starts_at__lt=end,
        ends_at__gt=start,
    )
    cells: dict[object, list[RoomCell]] = {room.pk: [] for room in rooms}
    for row in rows.order_by("starts_at", "pk"):
        cells[row.room_id].append(_cell_of(row, profile))
    return [RoomDay(room, cells[room.pk]) for room in rooms]


def _cell_of(row: Appointment, profile: ClinicianProfile) -> RoomCell:
    if row.clinician_id == profile.pk:
        return RoomCell(row.starts_at, row.ends_at, occupancy_label(row.patient.full_name), row.pk)
    return RoomCell(row.starts_at, row.ends_at, occupancy_label(None), None)
