"""Base of the management commands that run one job alone and print its counts."""

from datetime import UTC, datetime

from django.core.management.base import BaseCommand, CommandError

from scheduling.jobs.runner import Job, run_job


class JobCommand(BaseCommand):
    job: Job

    def handle(self, *args: object, **options: object) -> None:
        counts = run_job(self.job, datetime.now(UTC))
        if counts is None:
            raise CommandError(f"{self.job.name} failed; see the log line")
        self.stdout.write(" ".join(str(count) for count in counts.values()))
