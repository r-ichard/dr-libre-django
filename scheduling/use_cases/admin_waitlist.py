"""Section 10: the admin's waitlist list and the patient lookup its forms and the booking steps
share. Writes stay in `waitlist` and `placement`; these only read."""

from uuid import UUID

from django.db.models import Q

from scheduling.domain.search_ordering import Page, page_bounds
from scheduling.domain.vocabulary import Role
from scheduling.models import User, WaitlistEntry
from scheduling.use_cases.waitlist_inbox import with_details

PAGE_SIZE = 20
PATIENT_RESULTS = 20


def list_waitlist(status: str, page: int) -> Page[WaitlistEntry]:
    entries = with_details().select_related("patient")
    if status:
        entries = entries.filter(status=status)
    total = entries.count()
    bounds = page_bounds(total, page, PAGE_SIZE)
    shown = entries.order_by("created_at", "pk")[bounds.first : bounds.first + PAGE_SIZE]
    return Page(list(shown), total, bounds.page, bounds.page_count)


def search_patients(text: str) -> list[User]:
    """Active patients whose name or email holds the text; nothing for an empty text."""
    if not text:
        return []
    matching = Q(full_name__icontains=text) | Q(email__icontains=text)
    found = User.objects.filter(matching, role=Role.PATIENT, is_active=True)
    return list(found.order_by("full_name", "pk")[:PATIENT_RESULTS])


def active_patient(patient_id: UUID | None) -> User | None:
    if patient_id is None:
        return None
    return User.objects.filter(pk=patient_id, role=Role.PATIENT, is_active=True).first()
