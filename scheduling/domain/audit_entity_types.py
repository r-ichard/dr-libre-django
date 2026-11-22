"""The record types the product audits; the audit log filter lists exactly these."""

AUDITED_ENTITY_TYPES: frozenset[str] = frozenset({
    "ApiClient", "Appointment", "AppointmentType", "AvailabilityRule", "BookingHold",
    "ClinicianProfile", "DemoSeed", "Department", "Hospital", "Notification", "Room",
    "Session", "SignInFailure", "SignInLink", "Specialty", "TimeOff", "User", "WaitlistEntry",
})  # fmt: skip
