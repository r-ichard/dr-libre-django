"""Section 12.3: the record rule. Missing is not_found, someone else's is forbidden."""

from collections.abc import Callable

from scheduling.domain.failure import Failure, Result, Success


def guard_record[Record](
    record: Record | None, may_access: Callable[[Record], bool]
) -> Result[Record]:
    if record is None:
        return Failure.not_found()
    if not may_access(record):
        return Failure.forbidden()
    return Success(record)
