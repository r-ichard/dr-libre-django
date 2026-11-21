"""The stable demo world: organisations, people and what they offer. Pure data, no clock."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from scheduling.models.people import Role

ADMIN_EMAIL = "admin@example.test"
VERIFIED_AT = datetime(2026, 1, 1, tzinfo=UTC)
AVAILABLE_FROM = date(2026, 1, 1)
OPENING_TIME = time(9, 0)
CLOSING_TIME = time(17, 0)
WEEKDAYS_WORKED = (0, 1, 2, 3, 4)


@dataclass(frozen=True)
class HospitalSeed:
    code: str
    name: str
    city: str
    country: str
    time_zone: str
    phone: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class DepartmentSeed:
    code: str
    name: str
    hospital_code: str


@dataclass(frozen=True)
class RoomSeed:
    code: str
    name: str
    department_code: str
    floor: str
    equipment: tuple[str, ...]


@dataclass(frozen=True)
class SpecialtySeed:
    code: str
    name: str


@dataclass(frozen=True)
class AppointmentTypeSeed:
    code: str
    name: str
    department_code: str
    duration_minutes: int
    needs_room: bool
    is_bookable_online: bool
    colour: str


@dataclass(frozen=True)
class PersonSeed:
    email: str
    full_name: str
    role: Role
    phone: str
    has_password: bool = True


@dataclass(frozen=True)
class ClinicianSeed:
    email: str
    department_code: str
    specialty_code: str
    title: str
    default_room_code: str


HOSPITALS = (
    HospitalSeed("demo-berlin", "Spreeufer Demo Hospital", "Berlin", "Germany",
                 "Europe/Berlin", "+44 20 7946 0001", 52.52, 13.405),
    HospitalSeed("demo-newyork", "Harbour Demo Medical Center", "New York", "United States",
                 "America/New_York", "+44 20 7946 0002"),
    HospitalSeed("demo-sydney", "Bayside Demo Hospital", "Sydney", "Australia",
                 "Australia/Sydney", "+44 20 7946 0003", -33.8688, 151.2093),
)  # fmt: skip

DEPARTMENTS = (
    DepartmentSeed("demo-berlin-cardiology", "Cardiology", "demo-berlin"),
    DepartmentSeed("demo-berlin-dermatology", "Dermatology", "demo-berlin"),
    DepartmentSeed("demo-newyork-general", "General medicine", "demo-newyork"),
    DepartmentSeed("demo-sydney-paediatrics", "Paediatrics", "demo-sydney"),
)

ROOMS = (
    RoomSeed("demo-room-cardiology", "Heart room", "demo-berlin-cardiology", "1", ("ECG",)),
    RoomSeed(
        "demo-room-dermatology", "Skin room", "demo-berlin-dermatology", "2", ("Dermatoscope",)
    ),
    RoomSeed("demo-room-general", "Consulting room 4", "demo-newyork-general", "3", ()),
    RoomSeed("demo-room-paediatrics", "Play room", "demo-sydney-paediatrics", "G", ("Scales",)),
)

SPECIALTIES = (
    SpecialtySeed("demo-cardiology", "Cardiology"),
    SpecialtySeed("demo-dermatology", "Dermatology"),
    SpecialtySeed("demo-general-practice", "General practice"),
    SpecialtySeed("demo-paediatrics", "Paediatrics"),
    SpecialtySeed("demo-orthopaedics", "Orthopaedics"),
)

APPOINTMENT_TYPES = (
    AppointmentTypeSeed("demo-cardiology-consult", "Cardiology consultation",
                        "demo-berlin-cardiology", 30, True, True, "#c0392b"),
    AppointmentTypeSeed("demo-cardiology-phone", "Cardiology phone follow-up",
                        "demo-berlin-cardiology", 15, False, True, "#e67e22"),
    AppointmentTypeSeed("demo-skin-check", "Skin check",
                        "demo-berlin-dermatology", 20, True, False, "#8e44ad"),
    AppointmentTypeSeed("demo-general-checkup", "General check-up",
                        "demo-newyork-general", 30, True, True, "#2980b9"),
    AppointmentTypeSeed("demo-general-video", "General video visit",
                        "demo-newyork-general", 20, False, False, "#16a085"),
    AppointmentTypeSeed("demo-paediatric-visit", "Paediatric visit",
                        "demo-sydney-paediatrics", 30, True, True, "#27ae60"),
)  # fmt: skip

PEOPLE = (
    PersonSeed(ADMIN_EMAIL, "Ada Administrator", Role.ADMIN, ""),
    PersonSeed("clinician@example.test", "Dr Mira Falkenrath", Role.CLINICIAN, "+44 20 7946 0101"),
    PersonSeed(
        "clinician.heart@example.test", "Dr Oskar Lindqvist", Role.CLINICIAN, "+44 20 7946 0102"
    ),
    PersonSeed(
        "clinician.skin@example.test", "Dr Ines Valdermar", Role.CLINICIAN, "+44 20 7946 0103"
    ),
    PersonSeed(
        "clinician.general@example.test",
        "Dr Tobias Quillfeather",
        Role.CLINICIAN,
        "+44 20 7946 0104",
    ),
    PersonSeed(
        "clinician.child@example.test", "Dr Priya Wendelstein", Role.CLINICIAN, "+44 20 7946 0105"
    ),
    PersonSeed("patient@example.test", "Pia Passwort", Role.PATIENT, "+44 20 7946 0201"),
    PersonSeed(
        "passwordless@example.test", "Linus Linkfrei", Role.PATIENT, "+44 20 7946 0202", False
    ),
    PersonSeed("patient.three@example.test", "Greta Holm", Role.PATIENT, "+44 20 7946 0203", False),
    PersonSeed("patient.four@example.test", "Felix Ardent", Role.PATIENT, "", False),
    PersonSeed(
        "patient.five@example.test", "Noor Bellamy", Role.PATIENT, "+44 20 7946 0205", False
    ),
    PersonSeed(
        "patient.six@example.test", "Jonas Kestrel", Role.PATIENT, "+44 20 7946 0206", False
    ),
)

CLINICIANS = (
    ClinicianSeed("clinician@example.test", "demo-berlin-cardiology", "demo-cardiology",
                  "Consultant", "demo-room-cardiology"),
    ClinicianSeed("clinician.heart@example.test", "demo-berlin-cardiology", "demo-cardiology",
                  "Registrar", "demo-room-cardiology"),
    ClinicianSeed("clinician.skin@example.test", "demo-berlin-dermatology", "demo-dermatology",
                  "Consultant", "demo-room-dermatology"),
    ClinicianSeed("clinician.general@example.test", "demo-newyork-general", "demo-general-practice",
                  "Physician", "demo-room-general"),
    ClinicianSeed("clinician.child@example.test", "demo-sydney-paediatrics", "demo-paediatrics",
                  "Consultant", "demo-room-paediatrics"),
)  # fmt: skip
