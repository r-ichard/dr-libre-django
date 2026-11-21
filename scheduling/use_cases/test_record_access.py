"""Section 12.3: the record rule. Missing is not_found, someone else's is forbidden."""

from scheduling.domain.failure import Failure, Success
from scheduling.use_cases.record_access import guard_record


class _Note:
    def __init__(self, owner: str) -> None:
        self.owner = owner


def _owned_by_ada(note: _Note) -> bool:
    return note.owner == "ada"


def returns_not_found_when_record_is_missing() -> None:
    assert guard_record(None, _owned_by_ada) == Failure.not_found()


def returns_forbidden_when_record_belongs_to_someone_else() -> None:
    assert guard_record(_Note("grace"), _owned_by_ada) == Failure.forbidden()


def returns_record_when_actor_may_access() -> None:
    note = _Note("ada")

    assert guard_record(note, _owned_by_ada) == Success(note)
