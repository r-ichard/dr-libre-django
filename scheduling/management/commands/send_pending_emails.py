from scheduling.jobs.command import JobCommand
from scheduling.jobs.worker import SEND_PENDING_EMAILS


class Command(JobCommand):
    help = "Send the emails of notifications whose first send did not go through."
    job = SEND_PENDING_EMAILS
