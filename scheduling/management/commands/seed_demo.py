import os
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from scheduling.demo_seed.writer import seed_demo
from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.request_context import bind_request_context


class Command(BaseCommand):
    help = "Create or refresh the demo data. Refuses unless DEBUG is on."

    def handle(self, *args: object, **options: object) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_demo refuses to run when DEBUG is off")
        password = os.environ.get("DEMO_PASSWORD", "")
        if not password:
            raise CommandError("seed_demo needs DEMO_PASSWORD in the environment")
        now = timezone.now()
        # No request exists here, so the command makes the context a request would have made.
        with bind_request_context(RequestContext(uuid.uuid4().hex, now)):
            report = seed_demo(now, password)
        for model_name, count in sorted(report.built.items()):
            self.stdout.write(f"built {model_name}: {count}")
        for model_name, count in sorted(report.kept.items()):
            self.stdout.write(f"kept {model_name}: {count} (used by a person)")
        for scenario in report.skipped:
            self.stdout.write(f"skipped: {scenario}")
