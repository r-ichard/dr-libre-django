"""Builds the moving demo world by calling the use cases as the demo users.

Only `at_clock` rebinds the request context clock, around one call, then restores it.
A slot a person took between runs skips that seed and its follow-ups; any other refusal raises."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scheduling.demo_seed import scenarios
from scheduling.domain.failure import Failure, FailureCode, Result
from scheduling.domain.request_context import RequestContext
from scheduling.domain.vocabulary import AppointmentSource, AppointmentStatus, WaitlistStatus
from scheduling.models import (
    Appointment,
    AppointmentType,
    ClinicianProfile,
    Notification,
    User,
    WaitlistEntry,
)
from scheduling.use_cases.appointment_changes import cancel_appointment, change_status
from scheduling.use_cases.notification_inbox import mark_read
from scheduling.use_cases.placement import PlacementCommand, place_appointment
from scheduling.use_cases.request_context import bind_request_context, current_request_context
from scheduling.use_cases.waitlist import JoinCommand, accept_offer, join_waitlist
from scheduling.use_cases.waitlist_expiry import expire_waitlist

SLOT_TAKEN_CODES = frozenset(
    {FailureCode.CONFLICT, FailureCode.NO_ROOM_AVAILABLE, FailureCode.NO_CLINICIAN_AVAILABLE}
)
LEAD = timedelta(days=2)
CANCEL_REASON = "Patient asked to cancel"
STATUS_STEPS = {
    AppointmentStatus.CHECKED_IN: (AppointmentStatus.CHECKED_IN,),
    AppointmentStatus.COMPLETED: (AppointmentStatus.CHECKED_IN, AppointmentStatus.COMPLETED),
    AppointmentStatus.NO_SHOW: (AppointmentStatus.NO_SHOW,),
}
FINISHED = (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW)


class SeedBrokeRuleError(Exception):
    """A use case refused a seed for a reason other than a slot a person took."""


@contextmanager
def at_clock(moment: datetime) -> Iterator[None]:
    correlation_id = current_request_context().correlation_id
    with bind_request_context(RequestContext(correlation_id, moment)):
        yield


def expect[Row](result: Result[Row]) -> Row:
    """The row of a success; any refusal is a defect of the seed."""
    if isinstance(result, Failure):
        raise SeedBrokeRuleError(f"{result.code}: {result.details}")
    return result.value


def row_unless_slot_taken[Row](result: Result[Row]) -> Row | None:
    """The row of a success, None for a taken slot, a raise for any other refusal."""
    if isinstance(result, Failure) and result.code in SLOT_TAKEN_CODES:
        return None
    return expect(result)


@dataclass
class WorldBuilder:
    now: datetime
    users: dict[str, User]
    clinicians: dict[str, ClinicianProfile]
    types: dict[str, AppointmentType]
    joined: list[tuple[scenarios.WaitlistSeed, WaitlistEntry]] = field(default_factory=list)
    placed: list[tuple[scenarios.AppointmentSeed, Appointment]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def build(self) -> None:
        for seed in scenarios.APPOINTMENTS:
            self._book(seed)
        for entry_seed in scenarios.WAITLIST_ENTRIES:
            self._join(entry_seed)
        for seed, appointment in self.placed:
            self._change_status(seed, appointment)
        self._accept_offers()
        with at_clock(self.now):
            expire_waitlist()

    def _zone_of(self, type_code: str) -> ZoneInfo:
        return ZoneInfo(self.types[type_code].department.hospital.time_zone)

    def _booking_clock(self, starts_at: datetime) -> datetime:
        return min(self.now, starts_at - LEAD)

    def _book(self, seed: scenarios.AppointmentSeed) -> None:
        starts_at = scenarios.starts_at_for(self.now, self._zone_of(seed.type_code), seed)
        patient = self.users[seed.patient_email]
        clinician = self.clinicians[seed.clinician_email]
        named = None if seed.source == AppointmentSource.ROUND_ROBIN else clinician.pk
        actor = clinician.user if seed.source == AppointmentSource.STAFF else patient
        command = PlacementCommand(
            self.types[seed.type_code].pk, starts_at, named, patient.pk, None
        )
        with at_clock(self._booking_clock(starts_at)):
            appointment = row_unless_slot_taken(place_appointment(command, actor))
        if appointment is None:
            self.skipped.append(
                f"appointment {seed.type_code} day {seed.day_offset} at {seed.hour}"
            )
        else:
            self.placed.append((seed, appointment))

    def _join(self, seed: scenarios.WaitlistSeed) -> None:
        zone = self._zone_of(seed.type_code)
        preferred = seed.preferred_clinician_email
        command = JoinCommand(
            self.types[seed.type_code].pk,
            scenarios.local_midnight(self.now, zone, seed.earliest_offset),
            scenarios.local_midnight(self.now, zone, seed.latest_offset + 1),
            self.clinicians[preferred].pk if preferred else None,
            None,
        )
        joined_at = self.now
        if seed.joined_offset is not None:
            joined_at = scenarios.local_midnight(self.now, zone, seed.joined_offset)
        with at_clock(joined_at):
            entry = row_unless_slot_taken(join_waitlist(command, self.users[seed.patient_email]))
        if entry is None:
            self.skipped.append(f"waitlist {seed.type_code} for {seed.patient_email}")
        else:
            self.joined.append((seed, entry))

    def _change_status(self, seed: scenarios.AppointmentSeed, appointment: Appointment) -> None:
        staff = self.clinicians[seed.clinician_email].user
        starts_at = appointment.starts_at
        if seed.status == AppointmentStatus.CANCELLED:
            moment = self.now if starts_at > self.now else self._booking_clock(starts_at)
            with at_clock(moment):
                row_unless_slot_taken(cancel_appointment(appointment.pk, CANCEL_REASON, staff))
        for target in STATUS_STEPS.get(seed.status, ()):
            with at_clock(self.now):
                row_unless_slot_taken(change_status(appointment.pk, target, staff))
        if seed.status in FINISHED:
            self._read_notices(appointment)

    def _read_notices(self, appointment: Appointment) -> None:
        for notice in Notification.objects.filter(appointment=appointment):
            with at_clock(self.now):
                row_unless_slot_taken(mark_read(notice.pk, appointment.patient))

    def _accept_offers(self) -> None:
        for seed, entry in self.joined:
            entry.refresh_from_db()
            if seed.accepts and entry.status == WaitlistStatus.OFFERED:
                with at_clock(self.now):
                    row_unless_slot_taken(accept_offer(entry.pk, entry.patient))
