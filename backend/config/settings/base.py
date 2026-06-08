"""Base Django settings for BBTracker.

Environment-driven via django-environ. See .env.example at the repo root.
"""
from pathlib import Path

import environ

# backend/ directory (this file is config/settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
# In Docker, env vars come from compose's env_file. For bare-metal dev, read repo-root .env.
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # third-party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.headless",
    "axes",
    # local
    "apps.accounts",
    "apps.core",
    "apps.training",
    "apps.nutrition",
    "apps.protocols",
    "apps.diary",
    "apps.notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://bbtracker:bbtracker@db:5432/bbtracker",
    ),
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/0"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BBTracker API",
    "DESCRIPTION": "Self-coaching bodybuilding app API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- django-allauth (headless) ---
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # our custom User has no username field
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # dev only — require verification before real data
ACCOUNT_UNIQUE_EMAIL = True
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
HEADLESS_ONLY = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- CORS / CSRF (SvelteKit dev server origin) ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:5173"])
CSRF_COOKIE_HTTPONLY = False  # frontend must read csrftoken cookie to send X-CSRFToken
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --- django-axes (brute-force protection) ---
AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
AXES_FAILURE_LIMIT = 8
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True

# --- Progress-photo storage (MinIO via the S3 API) ---
# The backend reaches MinIO over the compose network at minio:9000. Photo bytes
# are streamed back through the owner-scoped API, so the bucket stays private
# (no public URLs). Tests set DIARY_STORAGE_BACKEND="memory" (see conftest.py).
DIARY_STORAGE_BACKEND = env("DIARY_STORAGE_BACKEND", default="s3")  # "s3" | "memory"
DIARY_S3_ENDPOINT = env("DIARY_S3_ENDPOINT", default="http://minio:9000")
DIARY_S3_ACCESS_KEY = env("MINIO_ROOT_USER", default="minioadmin")
DIARY_S3_SECRET_KEY = env("MINIO_ROOT_PASSWORD", default="minioadmin")
DIARY_S3_BUCKET = env("DIARY_S3_BUCKET", default="bbtracker-media")
DIARY_S3_REGION = env("DIARY_S3_REGION", default="us-east-1")

# Cap raw progress-photo uploads (Pillow re-encodes anyway).
DIARY_MAX_UPLOAD_BYTES = env.int("DIARY_MAX_UPLOAD_BYTES", default=15 * 1024 * 1024)

# --- Home Assistant notifications (personal, self-hosted) ---
# The reminder worker (manage.py run_reminders) posts to Home Assistant's REST
# API to deliver rest-timer + dose reminders. All optional: if unset, every
# notification is a silent no-op, so the app runs fine without Home Assistant.
HA_BASE_URL = env("HA_BASE_URL", default="")  # e.g. http://192.168.1.10:8123
HA_TOKEN = env("HA_TOKEN", default="")  # long-lived access token (keep secret)
HA_NOTIFY_SERVICE = env("HA_NOTIFY_SERVICE", default="notify")  # e.g. mobile_app_<device>
