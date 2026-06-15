"""
Development settings.
Uses SQLite by default so no external DB is needed to start developing.
Override DATABASE_URL in .env to use PostgreSQL locally.
Uses InMemoryChannelLayer so no Redis is needed for local chat testing.
"""

from .base import *  # noqa: F401, F403
from decouple import config
import dj_database_url

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Database — SQLite for local dev; set DATABASE_URL in .env for PostgreSQL
# ---------------------------------------------------------------------------
_db_url = config("DATABASE_URL", default="")
if _db_url:
    DATABASES = {
        "default": dj_database_url.parse(_db_url, conn_max_age=600)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

# ---------------------------------------------------------------------------
# Channel Layer — In-Memory for local dev (no Redis required)
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ---------------------------------------------------------------------------
# Email — console backend for development
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# CORS — allow all origins in dev for convenience
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
