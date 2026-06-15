"""
Chat WebSocket URL routing.

Registered in config/asgi.py under the ProtocolTypeRouter.
WebSocket requests to /ws/chat/{expense_id}/ are routed here.
"""

from django.urls import re_path

from apps.chat.consumers import ExpenseChatConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/chat/(?P<expense_id>\d+)/$",
        ExpenseChatConsumer.as_asgi(),
    ),
]
