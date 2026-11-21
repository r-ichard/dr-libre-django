from datetime import UTC, datetime
from uuid import uuid4

from django.core.management.base import BaseCommand

from scheduling.domain.request_context import RequestContext
from scheduling.use_cases.email_delivery import send_pending_emails
from scheduling.use_cases.request_context import bind_request_context

BATCH_SIZE = 100


class Command(BaseCommand):
    help = "Send the emails of notifications whose first send did not go through."

    def handle(self, *args: object, **options: object) -> None:
        context = RequestContext(correlation_id=uuid4().hex, now=datetime.now(UTC))
        with bind_request_context(context):
            sent = send_pending_emails(BATCH_SIZE)
        self.stdout.write(str(sent))
