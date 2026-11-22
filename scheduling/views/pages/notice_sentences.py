"""Section 10: the sentences of the admin notices, written at render from a code and an id, so
no name travels in a cookie. A subject that is gone reads as a generic noun."""

from uuid import UUID

from scheduling.use_cases import admin_record_reads, notice_subjects
from scheduling.views.pages.admin_record_kinds import KIND_VIEWS

APPOINTMENT_SENTENCES = {
    "booked": "Booked an appointment for {name}.",
    "checked_in": "Checked in the appointment of {name}.",
    "completed": "Completed the appointment of {name}.",
    "no_show": "Marked as no-show the appointment of {name}.",
    "cancelled": "Cancelled the appointment of {name}.",
    "rescheduled": "Rescheduled the appointment of {name}.",
}
WAITLIST_SENTENCES = {
    "waitlist_added": "Added {name} to the waitlist.",
    "waitlist_offered": "Offered a time to {name}.",
    "waitlist_accepted": "Accepted the offer for {name}.",
}
RECORD_SENTENCES = {
    "record_created": "Created the {noun} {name}.",
    "record_saved": "Saved the {noun} {name}.",
    "record_deleted": "Deleted the {noun}.",
}
NO_SUBJECT = UUID(int=0)
REMINDERS_PREFIX = "reminders:"


def notice_sentence(code: str, subject: str, kind: str) -> str:
    if code.startswith(REMINDERS_PREFIX):
        count = code.removeprefix(REMINDERS_PREFIX)
        return f"{count} {'reminder' if count == '1' else 'reminders'} created."
    subject_id = _uuid_of(subject)
    if code in APPOINTMENT_SENTENCES:
        return APPOINTMENT_SENTENCES[code].format(name=_patient_of_appointment(subject_id))
    if code in WAITLIST_SENTENCES:
        return WAITLIST_SENTENCES[code].format(name=_patient_of_entry(subject_id))
    if code == "user_deactivated":
        return f"Deactivated {_user_name(subject_id)}."
    if code in RECORD_SENTENCES and kind in KIND_VIEWS:
        return _record_sentence(code, kind, subject_id)
    return ""


def _uuid_of(text: str) -> UUID:
    try:
        return UUID(text)
    except ValueError:
        return NO_SUBJECT


def _patient_of_appointment(subject: UUID) -> str:
    return notice_subjects.patient_name_of_appointment(subject) or "the patient"


def _patient_of_entry(subject: UUID) -> str:
    return notice_subjects.patient_name_of_waitlist_entry(subject) or "the patient"


def _user_name(subject: UUID) -> str:
    return notice_subjects.user_name(subject) or "the user"


def _record_sentence(code: str, kind: str, subject: UUID) -> str:
    view = KIND_VIEWS[kind]
    saved = admin_record_reads.find_record(kind, subject) if subject != NO_SUBJECT else None
    name = ""
    if saved is not None:
        value: object = saved
        for part in view.title_accessor.split("."):
            value = getattr(value, part)
        name = str(value)
    return RECORD_SENTENCES[code].format(noun=view.singular, name=name)
