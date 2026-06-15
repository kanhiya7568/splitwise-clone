"""
Chat REST URL patterns.

Mounted at /api/ in config/urls.py.

GET /api/expenses/{expense_id}/messages/   — paginated message history
"""

from django.urls import path

from apps.chat.views import MessageHistoryView

urlpatterns = [
    path(
        "expenses/<int:expense_id>/messages/",
        MessageHistoryView.as_view(),
        name="message_history",
    ),
]
