"""Section 10: one table from record kind to the use cases that write it. The pages call the table
and never name a kind; the five task 18 kinds use the generic functions."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from scheduling.domain.failure import Result
from scheduling.models import User
from scheduling.use_cases.admin_clinicians import (
    attach_profile,
    delete_profile,
    profile_dependents,
    update_profile,
)
from scheduling.use_cases.admin_records import (
    RecordEdit,
    create_record,
    delete_record,
    dependents_of,
    update_record,
)
from scheduling.use_cases.admin_users import (
    create_user,
    delete_user,
    update_user,
    user_dependents,
)


@dataclass(frozen=True)
class Writers:
    create: Callable[[str, dict[str, object], User], Result[UUID]]
    update: Callable[[RecordEdit, User], Result[UUID]]
    delete: Callable[[str, UUID, User], Result[None]]
    dependents: Callable[[str, UUID, User], list[str]]


GENERIC = Writers(
    create_record,
    update_record,
    delete_record,
    lambda kind, record_id, _actor: dependents_of(kind, record_id),
)
WRITERS: dict[str, Writers] = {
    "hospital": GENERIC,
    "specialty": GENERIC,
    "department": GENERIC,
    "room": GENERIC,
    "appointment_type": GENERIC,
    "user": Writers(
        lambda _kind, values, actor: create_user(values, actor),
        update_user,
        lambda _kind, record_id, actor: delete_user(record_id, actor),
        lambda _kind, record_id, actor: user_dependents(record_id, actor.pk),
    ),
    "clinician": Writers(
        lambda _kind, values, actor: attach_profile(values, actor),
        update_profile,
        lambda _kind, record_id, actor: delete_profile(record_id, actor),
        lambda _kind, record_id, _actor: profile_dependents(record_id),
    ),
}
