from django.urls import path, re_path

from scheduling.views.api_view import NotFoundView
from scheduling.views.health import HealthView

urlpatterns = [
    path("api/v1/health", HealthView.as_view()),
    re_path(r"^api/v1/", NotFoundView.as_view()),
]
