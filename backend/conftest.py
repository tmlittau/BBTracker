import pytest


@pytest.fixture(autouse=True)
def _relax_external_deps_for_tests(settings):
    """Make tests independent of Redis and brute-force/rate limits."""
    settings.AXES_ENABLED = False
    settings.ACCOUNT_RATE_LIMITS = {}
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    # LocMemCache keeps data in a process-global keyed by location, so identical
    # configs share state across tests — clear it so cached reference data (e.g.
    # nutrients) can't leak between tests.
    from django.core.cache import cache

    cache.clear()
    # Progress-photo storage runs in-process (no MinIO/network) during tests.
    settings.DIARY_STORAGE_BACKEND = "memory"
    from apps.diary.storage import reset_storage_cache

    reset_storage_cache()
