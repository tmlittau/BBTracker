"""Production settings.

Runs behind Caddy (TLS-terminating reverse proxy) that is exposed only through a
Cloudflare Tunnel. See docker-compose.prod.yml, infra/caddy/Caddyfile and the
Deployment section of README.md.
"""
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE as _BASE_MIDDLEWARE
from .base import env

DEBUG = False

# --- HTTPS / proxy ---
# Caddy sets X-Forwarded-Proto=https, so request.is_secure() is true here even though
# the hop from the tunnel/Caddy to gunicorn is plain HTTP on the internal network.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HTTP->HTTPS redirect is enforced at the Cloudflare edge ("Always Use HTTPS").
# Left OFF by default so internal SSR calls (frontend -> backend over http) aren't
# redirected; `check --deploy` then reports only security.W008 (expected). Set
# DJANGO_SECURE_SSL_REDIRECT=1 if you front the app differently.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)

# --- Cookie / header hardening ---
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Static files ---
# WhiteNoise serves collected static (admin, DRF browsable API) straight from
# gunicorn — no shared volume between backend and Caddy required. Inserted directly
# after SecurityMiddleware as WhiteNoise requires.
_sec = _BASE_MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1
MIDDLEWARE = [
    *_BASE_MIDDLEWARE[:_sec],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *_BASE_MIDDLEWARE[_sec:],
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
