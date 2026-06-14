from .base import *  # noqa: F401,F403

DEBUG = True
INTERNAL_IPS = ["127.0.0.1"]

# Dev + tests use a local in-process cache so Redis isn't required to run the
# server or the suite (prod keeps the Redis cache from base). Sessions
# (cached_db) therefore fall back to the DB locally.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
