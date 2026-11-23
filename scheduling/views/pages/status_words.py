"""The one table of status words. A badge pairs a kind (colour and icon) with
a word, so colour is never the only signal."""

from scheduling.domain.vocabulary import AppointmentStatus, WaitlistStatus

BADGE_KINDS = {"success", "warning", "error", "information", "pending"}

APPOINTMENT_BADGES: dict[AppointmentStatus, tuple[str, str]] = {
    AppointmentStatus.BOOKED: ("information", "Booked"),
    AppointmentStatus.CONFIRMED: ("success", "Confirmed"),
    AppointmentStatus.CHECKED_IN: ("success", "Checked in"),
    AppointmentStatus.COMPLETED: ("information", "Completed"),
    AppointmentStatus.CANCELLED: ("error", "Cancelled"),
    AppointmentStatus.NO_SHOW: ("warning", "Missed"),
}
STAFF_APPOINTMENT_BADGES = {
    **APPOINTMENT_BADGES,
    AppointmentStatus.NO_SHOW: ("warning", "No-show"),
}
WAITLIST_BADGES: dict[WaitlistStatus, tuple[str, str]] = {
    WaitlistStatus.WAITING: ("pending", "Waiting"),
    WaitlistStatus.OFFERED: ("warning", "Offered"),
    WaitlistStatus.BOOKED: ("success", "Booked"),
    WaitlistStatus.EXPIRED: ("error", "Expired"),
}
ACTIVE_BADGE = ("success", "Active")
INACTIVE_BADGE = ("pending", "Inactive")
