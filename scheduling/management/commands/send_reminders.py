from scheduling.jobs.command import JobCommand
from scheduling.jobs.worker import SEND_REMINDERS


class Command(JobCommand):
    help = "Remind patients of appointments starting within 24 hours."
    job = SEND_REMINDERS
