import os
from datetime import timedelta
from pathlib import Path

try:
    import django_stubs_ext

    django_stubs_ext.monkeypatch()
except ImportError:
    pass
from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-fallback-key-for-dev-only")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "core",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.Require2FASetupMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "expense_month.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "expense_month.context_processors.script_prefix",
            ],
        },
    },
]

WSGI_APPLICATION = "expense_month.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.environ.get("DB_PATH", str(BASE_DIR / "db.sqlite3"))),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "expense_month.storage.VersionedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"
LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "two_factor:login"

TWO_FACTOR_REMEMBER_COOKIE_AGE = 60 * 60 * 24 * 30
TWO_FACTOR_REMEMBER_COOKIE_SECURE = True
TWO_FACTOR_REMEMBER_COOKIE_SAMESITE = "Lax"
TWO_FACTOR_PATCH_ADMIN = True

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ACCESS_FAILURE_LOG = True
AXES_LOCKOUT_TEMPLATE = "axes/lockout.html"

TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")
CAPTCHA_FAILURE_THRESHOLD = 3

FORCE_SCRIPT_NAME = os.environ.get("FORCE_SCRIPT_NAME", "") or None
if FORCE_SCRIPT_NAME:
    STATIC_URL = f"{FORCE_SCRIPT_NAME}/static/"

CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

STATIC_VERSION = os.environ.get("STATIC_VERSION", "")
