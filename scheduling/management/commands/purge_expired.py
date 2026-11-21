from scheduling.jobs.command import JobCommand
from scheduling.jobs.worker import PURGE_EXPIRED


class Command(JobCommand):
    help = "Delete expired sessions and sign-in failures older than the lockout window."
    job = PURGE_EXPIRED
