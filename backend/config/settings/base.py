"""
Base settings shared across all environments.

Structure:
    config/settings/base.py       ← this file (shared)
    config/settings/local.py      ← local development overrides
    config/settings/production.py ← production overrides

All sensitive values are read from environment variables via python-decouple.
Never hardcode secrets here.
"""

from datetime import timedelta
from pathlib import Path

from decouple import config

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
# BASE_DIR resolves to the backend/ directory (3 levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Security — overridden per environment
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-before-production")
DEBUG = False  # always False in base; set True only in local.py
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# ─────────────────────────────────────────────────────────────────────────────
# Installed Applications
#
# IMPORTANT: "daphne" must be listed BEFORE "django.contrib.staticfiles"
# This is enforced by daphne's system check (daphne.E001).
# ─────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # daphne must come first — it overrides the static-files runserver handler
    "daphne",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # enables JWT refresh token blacklisting
    "corsheaders",
    "django_filters",
    "channels",

    # Project apps
    "apps.users",
    "apps.authentication",
    "apps.groups",
    "apps.expenses",
    "apps.balances",
    "apps.settlements",
    "apps.chat",
]

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# corsheaders.middleware.CorsMiddleware must be as high as possible,
# and definitely before CommonMiddleware.
# ─────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ─────────────────────────────────────────────────────────────────────────────
# URL & ASGI/WSGI routing
# ─────────────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"  # used by Daphne

# ─────────────────────────────────────────────────────────────────────────────
# Templates (required for Django admin)
# ─────────────────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Custom User Model
# CRITICAL: Set before the very first migration. Never change after.
# ─────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

# ─────────────────────────────────────────────────────────────────────────────
# Password validation (Django built-in validators)
# Additional business rules (uppercase, digit) enforced in serializers.
# ─────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────────────────────
# Static files
# ─────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────────────────────────────────────
# Django REST Framework
# ─────────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # JWT authentication for all endpoints by default
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # All endpoints require authentication unless explicitly overridden
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Standard pagination: 20 items/page, max 100
    "DEFAULT_PAGINATION_CLASS": "utils.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    # Filtering, search, and ordering available on list endpoints
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Two-tier throttling: burst + sustained (NFR-04: 100 req/hour)
    "DEFAULT_THROTTLE_CLASSES": [
        "utils.throttling.UserBurstRateThrottle",
        "utils.throttling.UserSustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user_burst": "30/min",
        "user_sustained": "100/hour",
        "anon": "20/hour",
    },
    # JSON only — no BrowsableAPIRenderer in production
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # Unified {error, details} envelope for all error responses
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
}

# ─────────────────────────────────────────────────────────────────────────────
# SimpleJWT
# Access: 60 min  |  Refresh: 7 days  (per approved spec)
# ─────────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("ACCESS_TOKEN_LIFETIME_MINUTES", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,       # issue new refresh token on every refresh call
    "BLACKLIST_AFTER_ROTATION": True,    # old refresh token is immediately blacklisted
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ─────────────────────────────────────────────────────────────────────────────
# CORS
# Specific origins set in local.py / production.py
# ─────────────────────────────────────────────────────────────────────────────
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
).split(",")
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
