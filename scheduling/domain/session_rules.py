"""Section 12.2: how long a session lasts and when it is extended, as functions of now."""

from datetime import datetime, timedelta

from scheduling.models.access import SessionKind
from scheduling.models.people import Role

ADMIN_PASSWORD_LIFETIME = timedelta(hours=12)
PASSWORD_LIFETIME = timedelta(days=7)
LINK_OR_CODE_LIFETIME = timedelta(hours=24)


def session_lifetime(kind: SessionKind, role: Role) -> timedelta:
    if kind != SessionKind.PASSWORD:
        return LINK_OR_CODE_LIFETIME
    return ADMIN_PASSWORD_LIFETIME if role == Role.ADMIN else PASSWORD_LIFETIME


def extended_expiry(
    kind: SessionKind, role: Role, expires_at: datetime, now: datetime
) -> datetime | None:
    """A password session with less than half its lifetime left gets a full one; others never."""
    if kind != SessionKind.PASSWORD:
        return None
    lifetime = session_lifetime(kind, role)
    return now + lifetime if expires_at - now < lifetime / 2 else None
