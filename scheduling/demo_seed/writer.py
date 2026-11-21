"""Writes the demo world through the models. A row is found by its identity (see the plan) and
rewritten only when a value differs, so a second run changes nothing but the moving bookings."""

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Model

from scheduling.demo_seed import catalogue, scenarios
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    ClinicianProfile,
    Department,
    Hospital,
    Notification,
    Room,
    Specialty,
    TimeOff,
    User,
    WaitlistEntry,
)
from scheduling.models.booking import AppointmentStatus
from scheduling.use_cases.audit import AuditEvent, record_audit

AUDIT_ACTION = "demo_seed.run"


def seed_demo(now: datetime, password: str) -> dict[str, int]:
    """Row count per model; the counts are also the whole audit metadata."""
    with transaction.atomic():
        seeding = _Seeding(now, password)
        seeding.write_everything()
        counts = dict(seeding.counts)
        row_counts = {f"{name.lower()}_count": rows for name, rows in counts.items()}
        metadata = AuditMetadata(counts=row_counts)
        record_audit(AuditEvent(AUDIT_ACTION, "DemoSeed", "demo", metadata), None)
    return counts


class _Seeding:
    def __init__(self, now: datetime, password: str) -> None:
        self.now = now
        self.password = password
        self.counts: Counter[str] = Counter()
        self.hospitals: dict[str, Hospital] = {}
        self.departments: dict[str, Department] = {}
        self.rooms: dict[str, Room] = {}
        self.specialties: dict[str, Specialty] = {}
        self.types: dict[str, AppointmentType] = {}
        self.users: dict[str, User] = {}
        self.clinicians: dict[str, ClinicianProfile] = {}
        self.appointments: dict[scenarios.AppointmentKey, Appointment] = {}
        self.entries: dict[scenarios.WaitlistKey, WaitlistEntry] = {}

    def write_everything(self) -> None:
        self._organisation()
        self._people()
        self._availability_and_time_off()
        self._waitlist(offered=False)
        self._appointments()
        self._waitlist(offered=True)
        self._notifications()

    def _upsert[Row: Model](
        self, model: type[Row], lookup: Mapping[str, object], values: Mapping[str, object]
    ) -> Row:
        self.counts[model.__name__] += 1
        row = model._default_manager.filter(**lookup).first()
        if row is None:
            return model._default_manager.create(**lookup, **values)
        changed = {name: value for name, value in values.items() if getattr(row, name) != value}
        for name, value in changed.items():
            setattr(row, name, value)
        if changed:
            row.save()
        return row

    def _organisation(self) -> None:
        for hospital in catalogue.HOSPITALS:
            self.hospitals[hospital.code] = self._upsert(
                Hospital,
                {"code": hospital.code},
                {
                    "name": hospital.name, "street_address": "1 Example Street",
                    "postal_code": "00000", "city": hospital.city, "country": hospital.country,
                    "phone": hospital.phone, "time_zone": hospital.time_zone,
                    "latitude": hospital.latitude, "longitude": hospital.longitude,
                    "is_active": True,
                },
            )  # fmt: skip
        for department in catalogue.DEPARTMENTS:
            self.departments[department.code] = self._upsert(
                Department,
                {"code": department.code},
                {"name": department.name, "hospital": self.hospitals[department.hospital_code]},
            )
        for specialty in catalogue.SPECIALTIES:
            self.specialties[specialty.code] = self._upsert(
                Specialty, {"code": specialty.code}, {"name": specialty.name, "is_active": True}
            )
        for room in catalogue.ROOMS:
            self.rooms[room.code] = self._upsert(
                Room,
                {"code": room.code},
                {
                    "name": room.name, "floor": room.floor, "capacity": 1, "is_active": True,
                    "department": self.departments[room.department_code],
                    "equipment": list(room.equipment),
                },
            )  # fmt: skip
        for kind in catalogue.APPOINTMENT_TYPES:
            self.types[kind.code] = self._upsert(
                AppointmentType,
                {"code": kind.code},
                {
                    "name": kind.name, "duration_minutes": kind.duration_minutes,
                    "needs_room": kind.needs_room, "buffer_minutes": 5, "colour": kind.colour,
                    "is_bookable_online": kind.is_bookable_online, "is_active": True,
                    "department": self.departments[kind.department_code],
                },
            )  # fmt: skip

    def _people(self) -> None:
        for person in catalogue.PEOPLE:
            self.users[person.email] = self._user(person)
        for clinician in catalogue.CLINICIANS:
            self.clinicians[clinician.email] = self._upsert(
                ClinicianProfile,
                {"user": self.users[clinician.email]},
                {
                    "department": self.departments[clinician.department_code],
                    "specialty": self.specialties[clinician.specialty_code],
                    "title": clinician.title,
                    "default_room": self.rooms[clinician.default_room_code],
                },
            )

    def _user(self, person: catalogue.PersonSeed) -> User:
        user = self._upsert(
            User,
            {"email": person.email},
            {
                "full_name": person.full_name, "role": person.role, "phone": person.phone,
                "is_active": True, "email_verified_at": catalogue.VERIFIED_AT,
            },
        )  # fmt: skip
        if person.has_password:
            if not user.check_password(self.password):
                user.set_password(self.password)
                user.save()
        elif user.has_usable_password():
            user.set_unusable_password()
            user.save()
        return user

    def _availability_and_time_off(self) -> None:
        for clinician in self.clinicians.values():
            for weekday in catalogue.WEEKDAYS_WORKED:
                self._upsert(
                    AvailabilityRule,
                    {"clinician": clinician, "weekday": weekday},
                    {
                        "start_time": catalogue.OPENING_TIME, "end_time": catalogue.CLOSING_TIME,
                        "room": clinician.default_room, "valid_from": catalogue.AVAILABLE_FROM,
                        "valid_to": None,
                    },
                )  # fmt: skip
        for leave in scenarios.TIME_OFF:
            clinician = self.clinicians[leave.clinician_email]
            self._upsert(
                TimeOff,
                {"clinician": clinician, "reason": leave.reason},
                {
                    "starts_at": self._utc_midnight(leave.start_offset),
                    "ends_at": self._utc_midnight(leave.end_offset + 1),
                },
            )

    def _utc_midnight(self, day_offset: int) -> datetime:
        day = self.now.astimezone(UTC).date() + timedelta(days=day_offset)
        return datetime.combine(day, time.min, tzinfo=UTC)

    def _waitlist(self, *, offered: bool) -> None:
        for seed in scenarios.WAITLIST_ENTRIES:
            if (seed.offered is not None) != offered:
                continue
            preferred = seed.preferred_clinician_email
            self.entries[seed.key] = self._upsert(
                WaitlistEntry,
                {
                    "patient": self.users[seed.patient_email],
                    "appointment_type": self.types[seed.type_code],
                },
                {
                    "preferred_clinician": self.clinicians[preferred] if preferred else None,
                    "earliest_at": self._utc_midnight(seed.earliest_offset),
                    "latest_at": self._utc_midnight(seed.latest_offset),
                    "status": seed.status,
                    "offered_appointment": self.appointments[seed.offered]
                    if seed.offered
                    else None,
                },
            )

    def _appointments(self) -> None:
        for seed in scenarios.APPOINTMENTS:
            clinician = self.clinicians[seed.clinician_email]
            kind = self.types[seed.type_code]
            zone = ZoneInfo(clinician.department.hospital.time_zone)
            starts_at = scenarios.starts_at_for(self.now, zone, seed.day_offset, seed.hour)
            cancelled = seed.status == AppointmentStatus.CANCELLED
            entry = (
                self.entries[(seed.patient_email, seed.type_code)] if seed.from_waitlist else None
            )
            self.appointments[seed.key] = self._upsert(
                Appointment,
                {
                    "patient": self.users[seed.patient_email],
                    "clinician": clinician,
                    "appointment_type": kind,
                },
                {
                    "room": clinician.default_room if kind.needs_room else None,
                    "starts_at": starts_at,
                    "ends_at": starts_at + timedelta(minutes=kind.duration_minutes),
                    "status": seed.status,
                    "source": seed.source,
                    "cancelled_at": self._utc_midnight(0) if cancelled else None,
                    "cancellation_reason": "Patient asked to cancel" if cancelled else "",
                    "waitlist_entry": entry,
                },
            )

    def _notifications(self) -> None:
        for seed in scenarios.NOTIFICATIONS:
            appointment = self.appointments[seed.appointment] if seed.appointment else None
            entry = self.entries[seed.waitlist] if seed.waitlist else None
            self.counts[Notification.__name__] += 1
            Notification.objects.get_or_create(
                recipient=self.users[seed.recipient_email],
                kind=seed.kind,
                appointment=appointment,
                waitlist_entry=entry,
                defaults={"title": seed.title, "read_at": self.now if seed.is_read else None},
            )
