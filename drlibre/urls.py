from django.conf import settings
from django.shortcuts import redirect
from django.urls import path, re_path
from django.views.static import serve

from scheduling.views.api_view import NotFoundView
from scheduling.views.appointment_actions import (
    CancelView,
    CheckInView,
    CompleteView,
    NoShowView,
    RescheduleView,
)
from scheduling.views.appointments import AppointmentsView
from scheduling.views.auth import LinkVerifyView, LinkView, LoginView, LogoutView
from scheduling.views.booking import HoldsView, ResendView, VerifyView
from scheduling.views.health import HealthView
from scheduling.views.jobs import RemindersView
from scheduling.views.pages.booking_code import CodePage, ResendPage
from scheduling.views.pages.booking_confirmation import CalendarFile, ConfirmationPage
from scheduling.views.pages.booking_details import DetailsPage
from scheduling.views.pages.booking_times import TimesPage
from scheduling.views.pages.homes import AdminConsole, ClinicianWorkspace, PatientPortal
from scheduling.views.pages.public_pages import StylePage
from scheduling.views.pages.search_page import SearchPage
from scheduling.views.pages.sign_in import SignInPage
from scheduling.views.pages.sign_in_link import CheckEmailPage, LinkContinuePage, LinkRequestPage
from scheduling.views.pages.sign_out import SignOutPage
from scheduling.views.search import (
    SearchHospitalsView,
    SearchProvidersView,
    SearchSpecialtiesView,
)
from scheduling.views.slots import SlotsView
from scheduling.views.waitlist import AcceptView, OfferView, WaitlistView

handler403 = "scheduling.views.pages.errors.forbidden_page"
handler404 = "scheduling.views.pages.errors.not_found_page"
handler500 = "scheduling.views.pages.errors.server_error_page"

urlpatterns = [
    path("api/v1/health", HealthView.as_view()),
    path("api/v1/auth/login", LoginView.as_view()),
    path("api/v1/auth/logout", LogoutView.as_view()),
    path("api/v1/auth/link", LinkView.as_view()),
    path("api/v1/auth/link/verify", LinkVerifyView.as_view()),
    path("api/v1/slots", SlotsView.as_view()),
    path("api/v1/search/providers", SearchProvidersView.as_view()),
    path("api/v1/search/hospitals", SearchHospitalsView.as_view()),
    path("api/v1/search/specialties", SearchSpecialtiesView.as_view()),
    path("api/v1/booking/holds", HoldsView.as_view()),
    path("api/v1/booking/holds/<uuid:hold_id>/resend", ResendView.as_view()),
    path("api/v1/booking/holds/<uuid:hold_id>/verify", VerifyView.as_view()),
    path("api/v1/appointments", AppointmentsView.as_view()),
    path("api/v1/appointments/<uuid:appointment_id>/cancel", CancelView.as_view()),
    path("api/v1/appointments/<uuid:appointment_id>/reschedule", RescheduleView.as_view()),
    path("api/v1/appointments/<uuid:appointment_id>/check-in", CheckInView.as_view()),
    path("api/v1/appointments/<uuid:appointment_id>/complete", CompleteView.as_view()),
    path("api/v1/appointments/<uuid:appointment_id>/no-show", NoShowView.as_view()),
    path("api/v1/waitlist", WaitlistView.as_view()),
    path("api/v1/waitlist/<uuid:entry_id>/accept", AcceptView.as_view()),
    path("api/v1/waitlist/<uuid:entry_id>/offer", OfferView.as_view()),
    path("api/v1/jobs/reminders", RemindersView.as_view()),
    re_path(r"^api/v1/", NotFoundView.as_view()),
    path("", SearchPage.as_view()),
    path("favicon.ico", lambda request: redirect("/static/favicon.svg")),
    path("sign-in", SignInPage.as_view()),
    path("sign-in/email-link", LinkRequestPage.as_view()),
    path("sign-in/check-email", CheckEmailPage.as_view()),
    path("sign-in/link", LinkContinuePage.as_view()),
    path("sign-out", SignOutPage.as_view()),
    path("book/holds/<uuid:hold_id>/code", CodePage.as_view()),
    path("book/holds/<uuid:hold_id>/resend", ResendPage.as_view()),
    path("book/<uuid:appointment_type_id>", TimesPage.as_view()),
    path("book/<uuid:appointment_type_id>/details", DetailsPage.as_view()),
    path("appointments/<uuid:appointment_id>/confirmation", ConfirmationPage.as_view()),
    path("appointments/<uuid:appointment_id>/calendar.ics", CalendarFile.as_view()),
    path("patient/", PatientPortal.as_view()),
    path("clinician/", ClinicianWorkspace.as_view()),
    path("admin-console/", AdminConsole.as_view()),
    # Local-only product, so Django's development file server is enough and works with DEBUG off.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.BASE_DIR / "static"}),
]
if settings.DEBUG:
    urlpatterns.append(path("style", StylePage.as_view()))
