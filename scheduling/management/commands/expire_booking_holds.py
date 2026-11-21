from scheduling.jobs.command import JobCommand
from scheduling.jobs.worker import EXPIRE_BOOKING_HOLDS


class Command(JobCommand):
    help = "Remove booking holds past their expiry and audit each one."
    job = EXPIRE_BOOKING_HOLDS
