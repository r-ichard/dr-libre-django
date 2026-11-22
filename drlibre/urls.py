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
from scheduling.views.pages.booking_steps import ProviderChoicePage, ServicePage
from scheduling.views.pages.booking_times import TimesPage
from scheduling.views.pages.clinician_appointment import (
    AppointmentPage as ClinicianAppointmentPage,
)
from scheduling.views.pages.clinician_appointment import CancelPage as ClinicianCancelPage
from scheduling.views.pages.clinician_appointment import NotesPage
from scheduling.views.pages.clinician_availability import (
    AvailabilityPage,
    RuleDeletePage,
    RuleFormPage,
)
from scheduling.views.pages.clinician_calendar import CalendarPage, ColoursPage
from scheduling.views.pages.clinician_patients import PatientsPage
from scheduling.views.pages.clinician_reschedule import (
    ReschedulePage as ClinicianReschedulePage,
)
from scheduling.views.pages.clinician_reschedule import (
    RescheduleReviewPage as ClinicianRescheduleReviewPage,
)
from scheduling.views.pages.clinician_rooms import RoomsPage
from scheduling.views.pages.clinician_time_off import TimeOffDeletePage, TimeOffPage
from scheduling.views.pages.clinician_today import CheckInPage, CompletePage, NoShowPage, TodayPage
from scheduling.views.pages.detail_pages import HospitalPage, ProviderPage, SpecialtyPage
from scheduling.views.pages.homes import AdminConsole, PatientPortal
from scheduling.views.pages.patient_appointments import AppointmentsPage, CancelPage
from scheduling.views.pages.patient_notifications import (
    MarkAllReadPage,
    MarkReadPage,
    NotificationsPage,
)
from scheduling.views.pages.patient_profile import PasswordPage, ProfilePage
from scheduling.views.pages.patient_reschedule import ReschedulePage, RescheduleReviewPage
from scheduling.views.pages.patient_waitlist import AcceptOfferPage, WaitlistPage
from scheduling.views.pages.public_pages import StylePage
from scheduling.views.pages.search_page import SearchPage
from scheduling.views.pages.sign_in import SignInPage
from scheduling.views.pages.sign_in_link import CheckEmailPage, LinkContinuePage, LinkRequestPage
from scheduling.views.pages.sign_out import SignOutPage
from scheduling.views.public_details import (
    HospitalDetailView,
    ProviderDetailView,
    SpecialtyDetailView,
)
from scheduling.views.search import (
    SearchHospitalsView,
    SearchProvidersView,
    SearchSpecialtiesView,
)
from scheduling.views.slots import SlotsView
from scheduling.views.waitlist import AcceptView, OfferView, WaitlistView

handler400 = "scheduling.views.pages.errors.bad_request_page"
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
    path("api/v1/hospitals/<uuid:hospital_id>", HospitalDetailView.as_view()),
    path("api/v1/providers/<uuid:provider_id>", ProviderDetailView.as_view()),
    path("api/v1/specialties/<uuid:specialty_id>", SpecialtyDetailView.as_view()),
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
    path("providers/<uuid:provider_id>", ProviderPage.as_view()),
    path("hospitals/<uuid:hospital_id>", HospitalPage.as_view()),
    path("specialties/<uuid:specialty_id>", SpecialtyPage.as_view()),
    path("sign-in", SignInPage.as_view()),
    path("sign-in/email-link", LinkRequestPage.as_view()),
    path("sign-in/check-email", CheckEmailPage.as_view()),
    path("sign-in/link", LinkContinuePage.as_view()),
    path("sign-out", SignOutPage.as_view()),
    path("book/holds/<uuid:hold_id>/code", CodePage.as_view()),
    path("book/holds/<uuid:hold_id>/resend", ResendPage.as_view()),
    path("book", ServicePage.as_view()),
    path("book/<uuid:appointment_type_id>/provider", ProviderChoicePage.as_view()),
    path("book/<uuid:appointment_type_id>", TimesPage.as_view()),
    path("book/<uuid:appointment_type_id>/details", DetailsPage.as_view()),
    path("appointments/<uuid:appointment_id>/confirmation", ConfirmationPage.as_view()),
    path("appointments/<uuid:appointment_id>/calendar.ics", CalendarFile.as_view()),
    path("patient/", PatientPortal.as_view()),
    path("patient/appointments", AppointmentsPage.as_view()),
    path("patient/appointments/<uuid:appointment_id>/cancel", CancelPage.as_view()),
    path("patient/appointments/<uuid:appointment_id>/reschedule", ReschedulePage.as_view()),
    path(
        "patient/appointments/<uuid:appointment_id>/reschedule/review",
        RescheduleReviewPage.as_view(),
    ),
    path("patient/waitlist", WaitlistPage.as_view()),
    path("patient/waitlist/<uuid:entry_id>/accept", AcceptOfferPage.as_view()),
    path("patient/notifications", NotificationsPage.as_view()),
    path("patient/notifications/read-all", MarkAllReadPage.as_view()),
    path("patient/notifications/<uuid:notification_id>/read", MarkReadPage.as_view()),
    path("patient/profile", ProfilePage.as_view()),
    path("patient/profile/password", PasswordPage.as_view()),
    path("clinician/", TodayPage.as_view()),
    path("clinician/calendar", CalendarPage.as_view()),
    path("clinician/type-colours.css", ColoursPage.as_view()),
    path("clinician/availability", AvailabilityPage.as_view()),
    path("clinician/availability/new", RuleFormPage.as_view()),
    path("clinician/availability/<uuid:rule_id>/edit", RuleFormPage.as_view()),
    path("clinician/availability/<uuid:rule_id>/delete", RuleDeletePage.as_view()),
    path("clinician/time-off", TimeOffPage.as_view()),
    path("clinician/time-off/<uuid:time_off_id>/delete", TimeOffDeletePage.as_view()),
    path("clinician/patients", PatientsPage.as_view()),
    path("clinician/rooms", RoomsPage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>", ClinicianAppointmentPage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>/check-in", CheckInPage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>/complete", CompletePage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>/no-show", NoShowPage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>/cancel", ClinicianCancelPage.as_view()),
    path("clinician/appointments/<uuid:appointment_id>/notes", NotesPage.as_view()),
    path(
        "clinician/appointments/<uuid:appointment_id>/reschedule",
        ClinicianReschedulePage.as_view(),
    ),
    path(
        "clinician/appointments/<uuid:appointment_id>/reschedule/review",
        ClinicianRescheduleReviewPage.as_view(),
    ),
    path("admin-console/", AdminConsole.as_view()),
    # Local-only product, so Django's development file server is enough and works with DEBUG off.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.BASE_DIR / "static"}),
]
if settings.DEBUG:
    urlpatterns.append(path("style", StylePage.as_view()))
