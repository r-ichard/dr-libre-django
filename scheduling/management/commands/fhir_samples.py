import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from scheduling.domain.request_context import RequestContext
from scheduling.models import User
from scheduling.use_cases.request_context import bind_request_context
from scheduling.views.fhir.samples import write_samples


class Command(BaseCommand):
    help = "Write one sample of everything /fhir answers into a directory, from the demo seed."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("directory", type=Path)

    def handle(self, *args: object, **options: Path) -> None:
        admin = User.objects.filter(role="ADMIN", is_active=True).order_by("email").first()
        if admin is None:
            raise CommandError("no active admin: run seed_demo first")
        with bind_request_context(RequestContext(uuid.uuid4().hex, timezone.now())):
            written = write_samples(admin, options["directory"])
        self.stdout.write(f"wrote {len(written)} samples")
