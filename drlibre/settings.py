from pathlib import Path

from drlibre.environment import env_flag, require_env, require_env_list

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = require_env("SECRET_KEY")
DEBUG = env_flag("DEBUG")
ALLOWED_HOSTS = require_env_list("ALLOWED_HOSTS")
INSTALLED_APPS = ["rest_framework", "scheduling"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
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
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
