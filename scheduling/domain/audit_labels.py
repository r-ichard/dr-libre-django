"""Section 9.3: a plain label for each audit action shown in an appointment's history."""

AUDIT_LABELS = {
    "appointment.booked": "Booked",
    "appointment.check_in": "Checked in",
    "appointment.complete": "Completed",
    "appointment.no_show": "Marked as no-show",
    "appointment.cancel": "Cancelled",
    "appointment.cancelled": "Cancelled",
    "appointment.reschedule": "Rescheduled",
    "appointment.rescheduled": "Rescheduled",
    "appointment.note_save": "Clinical note saved",
}


def audit_label(action: str) -> str:
    return AUDIT_LABELS.get(action, action)
