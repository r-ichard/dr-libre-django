"""Writes the stable demo catalogue through the models (a row is found by its code or email and
rewritten only when a value differs) and the moving world through use cases, once a local day."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F, Model, Q, QuerySet

from scheduling.demo_seed import booking, catalogue, marker, scenarios
from scheduling.demo_seed.retire import retire_time_off, retire_world
from scheduling.domain.audit_metadata import AuditMetadata
from scheduling.domain.failure import Failure, FailureCode
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
from scheduling.use_cases.audit import AuditEvent, record_audit
from scheduling.use_cases.time_off import TimeOffCommand, create_time_off


@dataclass(frozen=True)
class SeedReport:
    built: dict[str, int]
    kept: dict[str, int]
    skipped: list[str]


def seed_demo(now: datetime, password: str) -> SeedReport:
    """What the run built, kept for a person and skipped; built counts are the audit metadata."""
    with transaction.atomic():
        seeding = _Seeding(now, password)
        seeding.write_everything()
        counts = seeding.built_counts()
        if seeding.rebuilt:
            row_counts = {f"{name.lower()}_count": rows for name, rows in counts.items()}
            metadata = AuditMetadata(counts=row_counts)
            record_audit(AuditEvent(marker.RUN_ACTION, "DemoSeed", "demo", metadata), None)
    return SeedReport(counts, dict(seeding.kept), seeding.skipped)


class _Seeding:
    def __init__(self, now: datetime, password: str) -> None:
        self.now = now
        self.password = password
        self.counts: Counter[str] = Counter()
        self.kept: Counter[str] = Counter()
        self.skipped: list[str] = []
        self.rebuilt = False
        self.made_appointments: list[Appointment] = []
        self.made_entries: list[WaitlistEntry] = []
        self.made_time_off: list[TimeOff] = []
        self.hospitals: dict[str, Hospital] = {}
        self.departments: dict[str, Department] = {}
        self.rooms: dict[str, Room] = {}
        self.specialties: dict[str, Specialty] = {}
        self.types: dict[str, AppointmentType] = {}
        self.users: dict[str, User] = {}
        self.clinicians: dict[str, ClinicianProfile] = {}

    def write_everything(self) -> None:
        self._organisation()
        self._people()
        self._availability()
        if marker.world_is_current(self.now):
            return
        self.kept = retire_time_off() + retire_world()
        self._time_off()
        builder = booking.WorldBuilder(self.now, self.users, self.clinicians, self.types)
        builder.build()
        self.skipped += builder.skipped
        joined = [entry.pk for _, entry in builder.joined]
        self.made_entries = list(WaitlistEntry.objects.filter(pk__in=joined))
        placed = Q(pk__in=[row.pk for _, row in builder.placed])
        self.made_appointments = list(
            Appointment.objects.filter(placed | Q(waitlist_entry__in=self.made_entries))
        )
        # The seed never mails: only its own rows are silenced, the on-commit send finds none.
        self._seeded_notices().filter(email_pending=True).update(
            email_pending=False, version=F("version") + 1
        )
        marker.record_marks(self.made_appointments, self.made_entries, self.made_time_off)
        self.rebuilt = True

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
            self._adopt_legacy_specialty(specialty.code)
            self.specialties[specialty.code] = self._upsert(
                Specialty, {"code": specialty.code}, {"name": specialty.name, "is_active": True}
            )
        self._drop_unused_legacy_specialties()
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

    def _adopt_legacy_specialty(self, code: str) -> None:
        """Older databases hold `demo-<code>`; renaming keeps the id and its clinicians."""
        legacy = Specialty.objects.filter(code=f"demo-{code}").first()
        if legacy is not None and not Specialty.objects.filter(code=code).exists():
            legacy.code = code
            legacy.save()

    def _drop_unused_legacy_specialties(self) -> None:
        unused = Specialty.objects.filter(code__startswith="demo-", clinicianprofile__isnull=True)
        unused.delete()

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

    def _availability(self) -> None:
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

    def _time_off(self) -> None:
        for leave in scenarios.TIME_OFF:
            clinician = self.clinicians[leave.clinician_email]
            zone = ZoneInfo(clinician.department.hospital.time_zone)
            command = TimeOffCommand(
                scenarios.local_midnight(self.now, zone, leave.start_offset),
                scenarios.local_midnight(self.now, zone, leave.end_offset + 1),
                leave.reason,
            )
            created = create_time_off(command, clinician.user)
            if isinstance(created, Failure) and created.code == FailureCode.INVALID_INPUT:
                self.skipped.append(f"time off {leave.start_offset} to {leave.end_offset}")
            else:
                self.made_time_off.append(booking.expect(created))

    def _seeded_notices(self) -> QuerySet[Notification]:
        return Notification.objects.filter(
            Q(appointment__in=self.made_appointments) | Q(waitlist_entry__in=self.made_entries)
        )

    def built_counts(self) -> dict[str, int]:
        notices = self._seeded_notices()
        return {
            **self.counts,
            Appointment.__name__: len(self.made_appointments),
            WaitlistEntry.__name__: len(self.made_entries),
            Notification.__name__: notices.count(),
            TimeOff.__name__: len(self.made_time_off),
        }
