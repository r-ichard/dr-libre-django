from pathlib import Path

from drlibre.environment import env_flag, require_env, require_env_list

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = require_env("SECRET_KEY")
DEBUG = env_flag("DEBUG")
ALLOWED_HOSTS = require_env_list("ALLOWED_HOSTS")
INSTALLED_APPS = ["django.contrib.postgres", "rest_framework", "scheduling"]
MIDDLEWARE = [
    "scheduling.views.middleware.RequestContextMiddleware",
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "drlibre.urls"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": require_env("DB_NAME"),
        "USER": require_env("DB_USER"),
        "PASSWORD": require_env("DB_PASSWORD"),
        "HOST": require_env("DB_HOST"),
        "PORT": require_env("DB_PORT"),
    }
}
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {"host": require_env("EMAIL_HOST"), "port": int(require_env("EMAIL_PORT"))},
    }
}
TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "scheduling.User"
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["scheduling.views.access.DenyUnlessDeclared"],
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "scheduling.views.negotiation.AlwaysJsonNegotiation",
    "EXCEPTION_HANDLER": "scheduling.views.failure_response.handle_exception",
    "UNAUTHENTICATED_USER": None,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "scheduling.views.json_logging.JsonFormatter"}},
    "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["stdout"], "level": "INFO"},
    # Django's own handlers interpolate paths into text; its records reach the JSON root instead.
    "loggers": {
        "django": {"handlers": [], "propagate": True},
        # The request middleware writes the one request line; this one runs outside its context.
        "django.request": {"handlers": [], "propagate": False},
        "django.server": {"handlers": [], "propagate": True},
    },
}
