"""
Production settings.

All values must come from environment variables.
No defaults for secrets — missing variables raise ImproperlyConfigured.

Required environment variables:
    SECRET_KEY
    DATABASE_URL
    REDIS_URL
    ALLOWED_HOSTS
    CORS_ALLOWED_ORIGINS

Optional environment variables (have safe defaults):
    ACCESS_TOKEN_LIFETIME_MINUTES  (default: 60)
    REFRESH_TOKEN_LIFETIME_DAYS    (default: 7)

Deployment: Render.com — start command uses Daphne (ASGI):
    daphne -b 0.0.0.0 -p $PORT config.asgi:application
"""

from .base import *  # noqa: F401, F403

import dj_database_url
from decouple import config

# ─────────────────────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────────────────────
DEBUG = False
SECRET_KEY = config("SECRET_KEY")  # raises UndefinedValueError if not set
ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")

# ─────────────────────────────────────────────────────────────────────────────
# HTTPS security headers
# ─────────────────────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ─────────────────────────────────────────────────────────────────────────────
# Database — Neon PostgreSQL
# Format: postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# Django Channels — Upstash Redis
# Format: rediss://:PASSWORD@HOST:PORT (TLS — note the double-s in rediss://)
# ─────────────────────────────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL")],
        },
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CORS — only the deployed Vercel frontend
# ─────────────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS").split(",")

# ─────────────────────────────────────────────────────────────────────────────
# Static files
# ─────────────────────────────────────────────────────────────────────────────
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
