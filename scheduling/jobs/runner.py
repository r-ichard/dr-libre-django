"""One job run: its own correlation id, its own instant, one JSON log line with the
counts. A failing job is logged and swallowed, so it never reaches the worker or another job."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from django.db import transaction

from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.request_context import bind_request_context

logger = logging.getLogger("scheduling.jobs")


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[], Mapping[str, int]]
    # The email job commits per notification itself; an outer transaction would roll back the
    # sent flags after the mail left, and the next run would send it again.
    atomic: bool = True


def run_job(job: Job, now: datetime) -> Mapping[str, int] | None:
    with bind_request_context(RequestContext(uuid4().hex, now)):
        try:
            counts = _execute(job)
        except Exception:
            logger.exception("job failed", extra={"job": job.name})
            return None
        logger.info("job finished", extra={"job": job.name, "counts": dict(counts)})
        return counts


def _execute(job: Job) -> Mapping[str, int]:
    if not job.atomic:
        return job.run()
    with transaction.atomic():
        return job.run()
