"""
WSGI configuration.

Used only by Django's development runserver as a fallback.
Production uses Daphne + ASGI (config/asgi.py).
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_wsgi_application()
