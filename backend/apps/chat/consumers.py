"""
Expense Chat WebSocket Consumer.

Endpoint: ws://host/ws/chat/{expense_id}/?token=<access_token>

Flow:
  CONNECT → authenticate JWT → check group membership → accept
          → send history (last HISTORY_LIMIT messages)

  RECEIVE {"type":"chat_message","content":"..."}
          → persist to DB → group_send to all consumers

  RECEIVE {"type":"delete_message","message_id":N}
          → soft-delete (sender only) → broadcast deletion event

  DISCONNECT → leave channel group

Transport ↔ DB boundary:
  All ORM access goes through standalone @database_sync_to_async functions
  defined at module level. The consumer itself contains only orchestration.

Channel group naming: chat_expense_{expense_id}
Close codes:
  4001 — unauthenticated (missing / invalid token)
  4003 — forbidden (not a group member)
  4004 — expense not found
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

HISTORY_LIMIT = 50


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers — standalone @database_sync_to_async functions
# ─────────────────────────────────────────────────────────────────────────────

@database_sync_to_async
def _db_get_user_from_token(token_str: str):
    """Validate access token and return User or None."""
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    User = get_user_model()
    try:
        validated = AccessToken(token_str)
        return User.objects.get(id=validated["user_id"], is_active=True)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return None


@database_sync_to_async
def _db_get_expense(expense_id: int):
    """Fetch non-deleted Expense or None."""
    from apps.expenses.models import Expense
    try:
        return Expense.objects.select_related("group").get(
            pk=expense_id, is_deleted=False
        )
    except Expense.DoesNotExist:
        return None


@database_sync_to_async
def _db_check_membership(group_id: int, user_id: int) -> bool:
    """Return True if user is an active member of the group."""
    from apps.groups.models import GroupMembership
    return GroupMembership.objects.filter(
        group_id=group_id, user_id=user_id, is_active=True
    ).exists()


@database_sync_to_async
def _db_get_message_history(expense_id: int, limit: int = HISTORY_LIMIT) -> list[dict]:
    """
    Return last `limit` messages for the expense, oldest-first (chat order).
    Soft-deleted messages are included but content is masked.
    """
    from apps.chat.models import Message
    messages = (
        Message.objects
        .filter(expense_id=expense_id)
        .select_related("sender")
        .order_by("-created_at")[:limit]
    )
    result = []
    for m in reversed(list(messages)):  # reverse to chronological order
        result.append(_serialize_message(m))
    return result


@database_sync_to_async
def _db_create_message(expense_id: int, user_id: int, content: str) -> dict:
    """Persist a new message and return its serialized form."""
    from apps.chat.models import Message
    message = Message.objects.create(
        expense_id=expense_id,
        sender_id=user_id,
        content=content,
    )
    # Refresh to get select_related sender data
    message = Message.objects.select_related("sender").get(pk=message.pk)
    return _serialize_message(message)


@database_sync_to_async
def _db_soft_delete_message(message_id: int, requesting_user_id: int) -> bool:
    """
    Soft-delete a message if the requesting user is the sender.
    Returns True if deletion happened, False otherwise.
    """
    from apps.chat.models import Message
    try:
        message = Message.objects.get(pk=message_id, is_deleted=False)
    except Message.DoesNotExist:
        return False
    if message.sender_id != requesting_user_id:
        return False
    message.soft_delete()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Serialization helper (sync — safe to call from async context)
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_message(message) -> dict:
    return {
        "id": message.id,
        "sender": {
            "id": message.sender.id,
            "email": message.sender.email,
            "first_name": message.sender.first_name,
            "last_name": message.sender.last_name,
        },
        "content": "[deleted]" if message.is_deleted else message.content,
        "is_deleted": message.is_deleted,
        "created_at": message.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Consumer
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for per-expense chat.

    One channel group per expense: chat_expense_{expense_id}
    All connected members of an expense receive each other's messages.
    """

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self):
        self.expense_id = int(self.scope["url_route"]["kwargs"]["expense_id"])
        self.room_group_name = f"chat_expense_{self.expense_id}"
        self.user = None

        # 1. Authenticate
        token = self._extract_token()
        if not token:
            await self.close(code=4001)
            return

        self.user = await _db_get_user_from_token(token)
        if not self.user:
            await self.close(code=4001)
            return

        # 2. Fetch expense
        self.expense = await _db_get_expense(self.expense_id)
        if not self.expense:
            await self.close(code=4004)
            return

        # 3. Check group membership
        is_member = await _db_check_membership(self.expense.group_id, self.user.id)
        if not is_member:
            await self.close(code=4003)
            return

        # 4. Join channel group and accept
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # 5. Send message history
        history = await _db_get_message_history(self.expense_id)
        await self.send(text_data=json.dumps({
            "type": "history",
            "messages": history,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = data.get("type")

        if msg_type == "chat_message":
            await self._handle_chat_message(data)
        elif msg_type == "delete_message":
            await self._handle_delete_message(data)

    # ── Message handlers ─────────────────────────────────────────────────────

    async def _handle_chat_message(self, data: dict) -> None:
        content = (data.get("content") or "").strip()
        if not content:
            return
        if len(content) > 1000:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Message exceeds 1000 character limit.",
            }))
            return

        message_data = await _db_create_message(self.expense_id, self.user.id, content)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message_data},
        )

    async def _handle_delete_message(self, data: dict) -> None:
        message_id = data.get("message_id")
        if not message_id:
            return

        deleted = await _db_soft_delete_message(int(message_id), self.user.id)
        if deleted:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "message_deleted", "message_id": message_id},
            )

    # ── Channel layer event handlers ─────────────────────────────────────────

    async def chat_message(self, event: dict) -> None:
        """Broadcast a new message to this WebSocket connection."""
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
        }))

    async def message_deleted(self, event: dict) -> None:
        """Broadcast a deletion event to this WebSocket connection."""
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"],
        }))

    # ── Private helpers ──────────────────────────────────────────────────────

    def _extract_token(self) -> str | None:
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        tokens = params.get("token", [])
        return tokens[0] if tokens else None
