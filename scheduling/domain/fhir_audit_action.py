"""The `AuditEvent.action` code of an audit action: R4 takes one code of AuditEventAction. The
product's own action name stays in `AuditEvent.type`; this maps it to the code."""

from dataclasses import dataclass

CREATE = "C"
READ = "R"
UPDATE = "U"
DELETE = "D"
EXECUTE = "E"

SUFFIX_CODES = {".create": CREATE, ".update": UPDATE, ".delete": DELETE}
EXPLICIT_CODES = {
    "appointment.book": CREATE,
    "appointment.booked": CREATE,
    "booking_hold.created": CREATE,
    "user.patient_created": CREATE,
    "waitlist.join": CREATE,
    "api_client.issue": CREATE,
    "appointment.export": READ,
    "notification.read": READ,
    "housekeeping.purge": DELETE,
    "booking_hold.expired": DELETE,
    "appointment.cancel": UPDATE,
    "appointment.cancelled": UPDATE,
    "appointment.reschedule": UPDATE,
    "appointment.rescheduled": UPDATE,
    "appointment.check_in": UPDATE,
    "appointment.complete": UPDATE,
    "appointment.no_show": UPDATE,
    "appointment.note_save": UPDATE,
    "api_client.revoke": UPDATE,
    "auth.password_change": UPDATE,
    "booking_hold.replaced": UPDATE,
    "profile.update": UPDATE,
    "specialty.renamed": UPDATE,
    "user.activate": UPDATE,
    "user.deactivate": UPDATE,
    "waitlist.accept": UPDATE,
    "waitlist.expire": UPDATE,
    "waitlist.offer": UPDATE,
    "waitlist.release": UPDATE,
}


def audit_action_code(action: str) -> str:
    """Operations that change no record of a person (sign-ins, runs, mail) and unknown actions are
    `E`, execute, so a new action is still valid FHIR before it has a row here."""
    if action in EXPLICIT_CODES:
        return EXPLICIT_CODES[action]
    for suffix, code in SUFFIX_CODES.items():
        if action.endswith(suffix):
            return code
    return EXECUTE


@dataclass(frozen=True)
class ActionsShowing:
    """The product actions an `AuditEvent.action` code shows: the named ones, the ones that end in
    a suffix, minus the named ones another code claims. `execute` is what no rule claims."""

    named: tuple[str, ...]
    suffixes: tuple[str, ...]
    claimed_elsewhere: tuple[str, ...]
    is_remainder: bool


def product_actions_of(code: str) -> ActionsShowing:
    """The inverse of `audit_action_code`, for a search that must find what the resource shows."""
    named = tuple(action for action, shown in EXPLICIT_CODES.items() if shown == code)
    elsewhere = tuple(action for action, shown in EXPLICIT_CODES.items() if shown != code)
    suffixes = tuple(suffix for suffix, shown in SUFFIX_CODES.items() if shown == code)
    return ActionsShowing(named, suffixes, elsewhere, code == EXECUTE)
