from pathlib import Path

from django.utils.csp import CSP

from drlibre.environment import env_flag, require_env, require_env_list

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = require_env("SECRET_KEY")
DEBUG = env_flag("DEBUG")
ALLOWED_HOSTS = require_env_list("ALLOWED_HOSTS")
INSTALLED_APPS = ["django.contrib.postgres", "rest_framework", "scheduling"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Outside the request middleware, which replaces an API 500 with a response of its own.
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "scheduling.views.middleware.RequestContextMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
# Section 16: scripts and styles are files the application serves itself, so nothing inline.
SECURE_CSP = {
    "default-src": [CSP.NONE],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "base-uri": [CSP.NONE],
    "frame-ancestors": [CSP.NONE],
    "object-src": [CSP.NONE],
}
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
HTTPS_ONLY = env_flag("HTTPS_ONLY")
SECURE_SSL_REDIRECT = HTTPS_ONLY
SECURE_HSTS_SECONDS = int(require_env("HSTS_SECONDS")) if HTTPS_ONLY else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS_ONLY
SECURE_HSTS_PRELOAD = HTTPS_ONLY
SESSION_COOKIE_SECURE = HTTPS_ONLY
CSRF_COOKIE_SECURE = HTTPS_ONLY
CSRF_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = "scheduling.views.pages.errors.csrf_failure_page"
ROOT_URLCONF = "drlibre.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
STATIC_URL = "/static/"
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
        "OPTIONS": {
            "host": require_env("EMAIL_HOST"),
            "port": int(require_env("EMAIL_PORT")),
            "timeout": 10,
        },
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
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "formatter": "json"},
        "discard": {"class": "logging.NullHandler"},
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
    # Django's request and server lines interpolate raw paths. A handler that discards, and no
    # propagation, also keeps Python's last-resort handler from printing them. The request
    # middleware writes the one request line and the trace.
    "loggers": {
        "django": {"handlers": [], "propagate": True},
        "django.request": {"handlers": ["discard"], "propagate": False},
        "django.server": {"handlers": ["discard"], "propagate": False},
    },
}
# Pages: Django refuses a larger form or more fields with its own 400; the API checks the same
# limits itself in scheduling/views/input_limits.py.
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
EMAIL_SENDER = require_env("EMAIL_SENDER")
PUBLIC_BASE_URL = require_env("PUBLIC_BASE_URL")
