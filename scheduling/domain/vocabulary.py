"""Section 3: the enumerations the pure rules speak in. Models store these same values."""

from enum import StrEnum


class AppointmentStatus(StrEnum):
    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class AppointmentSource(StrEnum):
    ONLINE = "ONLINE"
    ROUND_ROBIN = "ROUND_ROBIN"
    STAFF = "STAFF"


class Role(StrEnum):
    ADMIN = "ADMIN"
    CLINICIAN = "CLINICIAN"
    PATIENT = "PATIENT"


class SessionKind(StrEnum):
    PASSWORD = "PASSWORD"  # noqa: S105 - a kind of sign-in, not a secret
    EMAIL_LINK = "EMAIL_LINK"
    BOOKING_CODE = "BOOKING_CODE"
