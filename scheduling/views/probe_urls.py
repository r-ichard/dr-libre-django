from django.urls import path

from scheduling.views import probe_views
from scheduling.views.health import HealthView

urlpatterns = [
    path("api/v1/health", HealthView.as_view()),
    path("api/v1/probe/undeclared", probe_views.UndeclaredView.as_view()),
    path("api/v1/probe/explode", probe_views.ExplodingView.as_view()),
    path("api/v1/probe/patients/<str:email>", probe_views.IdentifierRouteView.as_view()),
    path("api/v1/probe/context", probe_views.ContextView.as_view()),
    path("api/v1/probe/conflict", probe_views.ConflictView.as_view()),
    path("api/v1/probe/write", probe_views.WriteView.as_view()),
    path("api/v1/probe/django-denied", probe_views.DjangoDeniedView.as_view()),
    path("api/v1/probe/auth-failed", probe_views.AuthenticationFailedView.as_view()),
    path("api/v1/probe/unsupported-media", probe_views.UnsupportedMediaView.as_view()),
]
