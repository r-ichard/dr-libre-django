from scheduling.jobs.command import JobCommand
from scheduling.jobs.worker import EXPIRE_WAITLIST


class Command(JobCommand):
    help = "Expire waitlist entries past their latest time and release stale offers."
    job = EXPIRE_WAITLIST
