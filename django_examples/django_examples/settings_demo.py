"""
Settings used by the automated demo video generator.

This keeps the runtime self-contained by using SQLite and local memory-backed
services instead of external containers.
"""

from .settings import *  # noqa: F401,F403


ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.demo.sqlite3",  # noqa: F405
    }
}

# The demo run does not require the debug toolbar, and removing it avoids
# optional runtime checks around internal IPs.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]  # noqa: F405
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "debug_toolbar.middleware.DebugToolbarMiddleware"
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "demo-video-cache",
    }
}

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
