import time
from datetime import UTC, datetime

from django.core.management.base import BaseCommand

from scheduling.jobs.worker import JOB_SCHEDULE, run_due_jobs

TICK_SECONDS = 1


class Command(BaseCommand):
    help = "Run the scheduled jobs until stopped."

    def handle(self, *args: object, **options: object) -> None:
        last_runs: dict[str, datetime] = {}
        while True:
            run_due_jobs(JOB_SCHEDULE, last_runs, datetime.now(UTC))
            time.sleep(TICK_SECONDS)
