"""
Local development settings.

Extends base.py with development-only overrides:
  - DEBUG = True
  - SQLite fallback (no PostgreSQL required to start)
  - InMemoryChannelLayer (no Redis required for local chat testing)
  - CORS allows all origins
  - BrowsableAPIRenderer enabled for dev convenience

Usage:
    python manage.py runserver          ← uses this file (default in manage.py)
    DJANGO_SETTINGS_MODULE=config.settings.local python manage.py ...
"""

from .base import *  # noqa: F401, F403

import dj_database_url
from decouple import config

# ─────────────────────────────────────────────────────────────────────────────
# Core overrides
# ─────────────────────────────────────────────────────────────────────────────
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# ─────────────────────────────────────────────────────────────────────────────
# Database
# If DATABASE_URL is set in .env, use PostgreSQL.
# Otherwise fall back to SQLite so the project starts with zero configuration.
# ─────────────────────────────────────────────────────────────────────────────
_db_url = config("DATABASE_URL", default="")

if _db_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _db_url,
            conn_max_age=600,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405 (BASE_DIR from base.py)
        }
    }

# ─────────────────────────────────────────────────────────────────────────────
# Django Channels — In-Memory channel layer
# No Redis dependency in local development.
# Switch to RedisChannelLayer by setting REDIS_URL in .env.
# ─────────────────────────────────────────────────────────────────────────────
_redis_url = config("REDIS_URL", default="")

if _redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_redis_url]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow all origins locally for convenience
# ─────────────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ─────────────────────────────────────────────────────────────────────────────
# DRF — add BrowsableAPIRenderer for local exploration
# ─────────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",  # removed in production
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Email — log to console instead of sending real emails
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"










import sys

# Disable DRF throttling during tests
if "test" in sys.argv:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
