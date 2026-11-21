import re
from dataclasses import dataclass
from datetime import datetime

CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


def is_sane_correlation_id(candidate: str) -> bool:
    return CORRELATION_ID_PATTERN.fullmatch(candidate) is not None


@dataclass(frozen=True)
class RequestContext:
    correlation_id: str
    now: datetime

    def __post_init__(self) -> None:
        if self.now.utcoffset() is None:
            raise ValueError("RequestContext.now must be timezone aware")
