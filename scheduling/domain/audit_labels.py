"""Section 9.3: a plain label for each audit action shown in an appointment's history."""

RECORD_WORDS = {
    "hospital": "Hospital",
    "specialty": "Specialty",
    "department": "Department",
    "room": "Room",
    "appointment_type": "Appointment type",
    "user": "User",
    "clinician": "Clinician profile",
}
VERB_WORDS = {"create": "created", "update": "updated", "delete": "deleted"}
USER_VERB_WORDS = {"deactivate": "deactivated", "activate": "activated"}

AUDIT_LABELS = {
    "api_client.issue": "API token issued",
    "api_client.revoke": "API token revoked",
    "appointment.book": "Booked",
    "appointment.booked": "Booked",
    "appointment.check_in": "Checked in",
    "appointment.complete": "Completed",
    "appointment.no_show": "Marked as no-show",
    "appointment.cancel": "Cancelled",
    "appointment.cancelled": "Cancelled",
    "appointment.reschedule": "Rescheduled",
    "appointment.rescheduled": "Rescheduled",
    "appointment.export": "Appointments exported",
    "appointment.note_save": "Clinical note saved",
    **{
        f"{record}.{verb}": f"{noun} {past}"
        for record, noun in RECORD_WORDS.items()
        for verb, past in VERB_WORDS.items()
    },
    **{f"user.{verb}": f"User {past}" for verb, past in USER_VERB_WORDS.items()},
    "auth.link_refused": "Sign-in link refused",
    "auth.link_requested": "Sign-in link requested",
    "auth.link_used": "Signed in with a link",
    "auth.lockout": "Locked out after failed sign-ins",
    "auth.login": "Signed in",
    "auth.login_failed": "Sign-in failed",
    "auth.logout": "Signed out",
    "auth.password_change": "Password changed",
    "availability.create": "Availability added",
    "availability.delete": "Availability removed",
    "availability.update": "Availability changed",
    "booking_code.verification_failed": "Email code not accepted",
    "booking_hold.created": "Time held for booking",
    "booking_hold.expired": "Held time released",
    "booking_hold.replaced": "Held time replaced",
    "clinician.round_robin_assigned": "Clinician assigned",
    "demo_seed.mark": "Demo data marked",
    "demo_seed.run": "Demo data loaded",
    "housekeeping.purge": "Old records removed",
    "notification.email_sent": "Email sent",
    "notification.read": "Notification read",
    "profile.update": "Profile changed",
    "reminder.run": "Reminders sent",
    "specialty.renamed": "Specialty renamed",
    "time_off.create": "Time off recorded",
    "time_off.delete": "Time off removed",
    "user.patient_created": "Patient account created",
    "waitlist.accept": "Waitlist offer accepted",
    "waitlist.expire": "Waitlist entry expired",
    "waitlist.join": "Joined the waitlist",
    "waitlist.offer": "Waitlist offer made",
    "waitlist.release": "Waitlist offer released",
}

UNKNOWN_LABEL = "Changed the record"


def audit_label(action: str) -> str:
    return AUDIT_LABELS.get(action, UNKNOWN_LABEL)
