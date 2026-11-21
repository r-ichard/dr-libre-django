from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve

from scheduling.views.api_view import NotFoundView
from scheduling.views.auth import LoginView, LogoutView
from scheduling.views.health import HealthView
from scheduling.views.pages.homes import AdminConsole, ClinicianWorkspace, PatientPortal
from scheduling.views.pages.public_pages import RootPage, StylePage
from scheduling.views.pages.sign_in import SignInPage
from scheduling.views.pages.sign_out import SignOutPage

handler403 = "scheduling.views.pages.errors.forbidden_page"
handler404 = "scheduling.views.pages.errors.not_found_page"
handler500 = "scheduling.views.pages.errors.server_error_page"

urlpatterns = [
    path("api/v1/health", HealthView.as_view()),
    path("api/v1/auth/login", LoginView.as_view()),
    path("api/v1/auth/logout", LogoutView.as_view()),
    re_path(r"^api/v1/", NotFoundView.as_view()),
    path("", RootPage.as_view()),
    path("sign-in", SignInPage.as_view()),
    path("sign-out", SignOutPage.as_view()),
    path("patient/", PatientPortal.as_view()),
    path("clinician/", ClinicianWorkspace.as_view()),
    path("admin-console/", AdminConsole.as_view()),
    # Local-only product, so Django's development file server is enough and works with DEBUG off.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.BASE_DIR / "static"}),
]
if settings.DEBUG:
    urlpatterns.append(path("style", StylePage.as_view()))
