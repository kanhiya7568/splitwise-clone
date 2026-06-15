"""
Chat app models: Message.

Messages are attached to an Expense (not a Group).
This scopes chat to the context of a specific expense, as per approved spec.

Real-time delivery: Django Channels (Module 9).
REST history: GET /api/expenses/{id}/messages/ (Module 9).
Soft-delete: is_deleted=True — content replaced with "[deleted]" in responses.
"""

from django.conf import settings
from django.db import models


class Message(models.Model):
    expense = models.ForeignKey(
        "expenses.Expense",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_messages",
    )
    # Max 1000 characters per approved spec (FR-CHT-02)
    content = models.TextField(max_length=1000)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        # Chronological order for chat display
        ordering = ["created_at"]
        indexes = [
            # Primary query: all messages for an expense, in order
            models.Index(fields=["expense", "created_at"], name="message_expense_time_idx"),
        ]

    def __str__(self) -> str:
        preview = self.content[:40] + ("..." if len(self.content) > 40 else "")
        return f"[{self.sender}] {preview}"

    def soft_delete(self) -> None:
        """Mark message as deleted. Content is preserved in DB for audit."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])
