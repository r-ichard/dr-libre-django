"""Spec 15.4: issue, list and revoke API tokens from a shell. Only `issue` prints the token, once;
no output ever carries a hash. The actor of the audit entry is empty: a shell is not a user."""

import uuid
from argparse import ArgumentParser

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from scheduling.domain.failure import Failure
from scheduling.domain.request_context import RequestContext
from scheduling.models import User
from scheduling.use_cases.api_tokens import issue_token, list_tokens, revoke_token
from scheduling.use_cases.request_context import bind_request_context

NAME_LIMIT = 100


class Command(BaseCommand):
    help = "Issue, list or revoke API tokens."

    def add_arguments(self, parser: ArgumentParser) -> None:
        actions = parser.add_subparsers(dest="action", required=True)
        issue = actions.add_parser("issue", help="make a token for an active user")
        issue.add_argument("email")
        issue.add_argument("--name", required=True)
        actions.add_parser("list", help="show tokens without any secret")
        revoke = actions.add_parser("revoke", help="stop a token from working")
        revoke.add_argument("client_id")

    def handle(self, *args: object, **options: str) -> None:
        context = RequestContext(uuid.uuid4().hex, timezone.now())
        with bind_request_context(context):
            action = options["action"]
            if action == "issue":
                self._issue(options["email"], options["name"].strip())
            elif action == "list":
                self._list()
            else:
                self._revoke(options["client_id"])

    def _issue(self, email: str, name: str) -> None:
        user = User.objects.filter(email=email.strip().lower(), is_active=True).first()
        if user is None:
            raise CommandError("no active user has that email")
        if not 1 <= len(name) <= NAME_LIMIT:
            raise CommandError(f"the name needs 1 to {NAME_LIMIT} characters")
        self.stdout.write(issue_token(user, name).token)

    def _list(self) -> None:
        for client in list_tokens():
            state = "revoked" if client.revoked_at else "active"
            self.stdout.write(f"{client.pk} {state} user={client.user_id} {client.name}")

    def _revoke(self, raw_id: str) -> None:
        try:
            client_id = uuid.UUID(raw_id)
        except ValueError:
            raise CommandError("the id is not a token id") from None
        if isinstance(revoke_token(client_id), Failure):
            raise CommandError("no token has that id")
