"""
ASGI configuration — entry point for Daphne.

ProtocolTypeRouter dispatches:
  http       → Standard Django request/response handler
  websocket  → Django Channels URLRouter → ChatConsumer

AllowedHostsOriginValidator rejects WebSocket connections from
origins not in ALLOWED_HOSTS (security layer before authentication).

AuthMiddlewareStack populates scope["user"] via Django session auth —
not used for this project (JWT query-param auth is used in the consumer
instead), but included for forward compatibility.

Production start command (Procfile):
    daphne -b 0.0.0.0 -p $PORT config.asgi:application
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

# Django must be set up before importing channels or app-level modules.
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

# WebSocket URL patterns are defined in apps/chat/routing.py.
# Imported after Django setup to avoid AppRegistryNotReady errors.
from apps.chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
