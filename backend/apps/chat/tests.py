"""
Chat tests — Module 9.

Tests cover:
  - DB helper functions (sync, no WebSocket)
  - REST API (MessageHistoryView)
  - WebSocket consumer (via channels.testing.WebsocketCommunicator)

Run: python manage.py test apps.chat
"""

import json
from datetime import date
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.chat.consumers import (
    _db_check_membership,
    _db_create_message,
    _db_get_message_history,
    _db_get_user_from_token,
    _db_soft_delete_message,
)
from apps.chat.models import Message
from apps.expenses.models import Expense
from apps.groups.models import Group, GroupMembership
from apps.users.models import User

CHANNEL_LAYERS_SETTING = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def mk_user(email):
    return User.objects.create_user(
        email=email, password="Pass1word", first_name="T", last_name="U"
    )


def auth_header(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


from asgiref.sync import async_to_sync, sync_to_async

@sync_to_async
def access_token_str(user):
    return str(RefreshToken.for_user(user).access_token)

def mk_group(creator):
    g = Group.objects.create(name="G", created_by=creator)
    GroupMembership.objects.create(group=g, user=creator, role=GroupMembership.ROLE_ADMIN)
    return g


def add_member(group, user):
    GroupMembership.objects.create(group=group, user=user, role=GroupMembership.ROLE_MEMBER)


def mk_expense(group, user):
    return Expense.objects.create(
        group=group, paid_by=user, created_by=user,
        description="X", amount=Decimal("50.00"),
        category=Expense.CATEGORY_FOOD, expense_date=date.today(),
        split_type=Expense.SPLIT_EQUAL,
    )


def mk_message(expense, sender, content="Hello"):
    return Message.objects.create(expense=expense, sender=sender, content=content)


def ws_url(expense_id, token=None):
    url = f"/ws/chat/{expense_id}/"
    if token:
        url += f"?token={token}"
    return url


# ─── DB Helper Unit Tests ─────────────────────────────────────────────────────

class DBHelperTests(TestCase):
    def setUp(self):
        self.user = mk_user("db_u@x.com")
        self.group = mk_group(self.user)
        self.expense = mk_expense(self.group, self.user)

    def _run(self, coro):
        return async_to_sync(lambda: coro)()

    def test_get_user_from_valid_token(self):
        token = str(RefreshToken.for_user(self.user).access_token)
        user = async_to_sync(_db_get_user_from_token)(token)
        self.assertEqual(user.id, self.user.id)

    def test_get_user_from_invalid_token(self):
        user = async_to_sync(_db_get_user_from_token)("bad.token.here")
        self.assertIsNone(user)

    def test_get_user_from_empty_token(self):
        user = async_to_sync(_db_get_user_from_token)("")
        self.assertIsNone(user)

    def test_check_membership_active_member(self):
        result = async_to_sync(_db_check_membership)(self.group.id, self.user.id)
        self.assertTrue(result)

    def test_check_membership_outsider(self):
        outsider = mk_user("db_out@x.com")
        result = async_to_sync(_db_check_membership)(self.group.id, outsider.id)
        self.assertFalse(result)

    def test_check_membership_removed_member(self):
        member = mk_user("db_rem@x.com")
        m = GroupMembership.objects.create(group=self.group, user=member, role=GroupMembership.ROLE_MEMBER)
        m.deactivate()
        result = async_to_sync(_db_check_membership)(self.group.id, member.id)
        self.assertFalse(result)

    def test_create_message_persists(self):
        data = async_to_sync(_db_create_message)(self.expense.id, self.user.id, "Hi!")
        self.assertTrue(Message.objects.filter(expense=self.expense, content="Hi!").exists())
        self.assertEqual(data["content"], "Hi!")

    def test_create_message_returns_sender_info(self):
        data = async_to_sync(_db_create_message)(self.expense.id, self.user.id, "Hey")
        self.assertIn("id", data["sender"])
        self.assertEqual(data["sender"]["email"], self.user.email)

    def test_get_message_history_chronological(self):
        mk_message(self.expense, self.user, "First")
        mk_message(self.expense, self.user, "Second")
        history = async_to_sync(_db_get_message_history)(self.expense.id)
        contents = [m["content"] for m in history]
        self.assertEqual(contents, ["First", "Second"])

    def test_get_message_history_masks_deleted(self):
        m = mk_message(self.expense, self.user, "Deleted content")
        m.soft_delete()
        history = async_to_sync(_db_get_message_history)(self.expense.id)
        self.assertEqual(history[0]["content"], "[deleted]")

    def test_get_message_history_limit(self):
        for i in range(60):
            mk_message(self.expense, self.user, f"Msg {i}")
        history = async_to_sync(_db_get_message_history)(self.expense.id, limit=50)
        self.assertEqual(len(history), 50)

    def test_soft_delete_message_by_sender(self):
        m = mk_message(self.expense, self.user)
        result = async_to_sync(_db_soft_delete_message)(m.id, self.user.id)
        self.assertTrue(result)
        m.refresh_from_db()
        self.assertTrue(m.is_deleted)

    def test_soft_delete_message_by_non_sender_fails(self):
        other = mk_user("db_other@x.com")
        m = mk_message(self.expense, self.user)
        result = async_to_sync(_db_soft_delete_message)(m.id, other.id)
        self.assertFalse(result)
        m.refresh_from_db()
        self.assertFalse(m.is_deleted)

    def test_soft_delete_already_deleted_fails(self):
        m = mk_message(self.expense, self.user)
        m.soft_delete()
        result = async_to_sync(_db_soft_delete_message)(m.id, self.user.id)
        self.assertFalse(result)


# ─── REST API Tests ───────────────────────────────────────────────────────────

class MessageHistoryAPITests(APITestCase):
    def setUp(self):
        self.member = mk_user("api_m@x.com")
        self.outsider = mk_user("api_out@x.com")
        self.group = mk_group(self.member)
        self.expense = mk_expense(self.group, self.member)
        self.url = reverse("message_history", kwargs={"expense_id": self.expense.pk})
        for i in range(3):
            mk_message(self.expense, self.member, f"Msg{i}")

    def test_member_can_list_200(self):
        r = self.client.get(self.url, **auth_header(self.member))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 3)

    def test_outsider_gets_403(self):
        r = self.client.get(self.url, **auth_header(self.outsider))
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_401(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 401)

    def test_chronological_ordering(self):
        r = self.client.get(self.url, **auth_header(self.member))
        results = r.json()["results"]
        ids = [m["id"] for m in results]
        self.assertEqual(ids, sorted(ids))

    def test_deleted_message_content_masked(self):
        m = mk_message(self.expense, self.member, "Secret")
        m.soft_delete()
        r = self.client.get(self.url, **auth_header(self.member))
        contents = [item["content"] for item in r.json()["results"]]
        self.assertIn("[deleted]", contents)
        self.assertNotIn("Secret", contents)

    def test_deleted_expense_returns_404(self):
        self.expense.soft_delete()
        r = self.client.get(self.url, **auth_header(self.member))
        self.assertEqual(r.status_code, 404)

    def test_pagination_present(self):
        r = self.client.get(self.url, **auth_header(self.member))
        data = r.json()
        self.assertIn("count", data)
        self.assertIn("results", data)

    def test_cross_expense_isolation(self):
        exp2 = mk_expense(self.group, self.member)
        mk_message(exp2, self.member, "Other expense msg")
        r = self.client.get(self.url, **auth_header(self.member))
        self.assertEqual(r.json()["count"], 3)  # only original 3

    def test_cross_group_isolation(self):
        other_user = mk_user("cgi_u@x.com")
        group2 = mk_group(other_user)
        exp2 = mk_expense(group2, other_user)
        url2 = reverse("message_history", kwargs={"expense_id": exp2.pk})
        r = self.client.get(url2, **auth_header(self.member))
        self.assertEqual(r.status_code, 403)


# ─── WebSocket Consumer Tests ─────────────────────────────────────────────────

@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_SETTING)
class WebSocketConnectionTests(TransactionTestCase):
    """Tests for WebSocket connection lifecycle."""

    def setUp(self):
        self.user = mk_user("ws_u@x.com")
        self.group = mk_group(self.user)
        self.expense = mk_expense(self.group, self.user)

    def _get_application(self):
        from channels.routing import ProtocolTypeRouter, URLRouter
        from apps.chat.routing import websocket_urlpatterns
        return ProtocolTypeRouter({"websocket": URLRouter(websocket_urlpatterns)})

    def test_authenticated_member_connects(self):
        async def _test():
            app = self._get_application()
            token = await access_token_str(self.user)
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.disconnect()
        async_to_sync(_test)()

    def test_unauthenticated_rejected(self):
        async def _test():
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(self.expense.id))  # no token
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)
        async_to_sync(_test)()

    def test_invalid_token_rejected(self):
        async def _test():
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, "bad.token"))
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)
        async_to_sync(_test)()

    def test_non_member_rejected(self):
        async def _test():
            outsider = await sync_to_async(mk_user)("ws_out@x.com")
            token = await access_token_str(outsider)
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4003)
        async_to_sync(_test)()

    def test_nonexistent_expense_rejected(self):
        async def _test():
            token = await access_token_str(self.user)
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(99999, token))
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4004)
        async_to_sync(_test)()

    def test_history_sent_on_connect(self):
        mk_message(self.expense, self.user, "Old message")

        async def _test():
            token = await access_token_str(self.user)
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "history")
            self.assertEqual(len(response["messages"]), 1)
            self.assertEqual(response["messages"][0]["content"], "Old message")
            await comm.disconnect()
        async_to_sync(_test)()

    def test_empty_history_on_connect(self):
        async def _test():
            token = await access_token_str(self.user)
            app = self._get_application()
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            await comm.connect()
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "history")
            self.assertEqual(response["messages"], [])
            await comm.disconnect()
        async_to_sync(_test)()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_SETTING)
class WebSocketMessagingTests(TransactionTestCase):
    """Tests for message send/receive/delete over WebSocket."""

    def setUp(self):
        self.user_a = mk_user("wm_a@x.com")
        self.user_b = mk_user("wm_b@x.com")
        self.group = mk_group(self.user_a)
        add_member(self.group, self.user_b)
        self.expense = mk_expense(self.group, self.user_a)

    def _get_application(self):
        from channels.routing import ProtocolTypeRouter, URLRouter
        from apps.chat.routing import websocket_urlpatterns
        return ProtocolTypeRouter({"websocket": URLRouter(websocket_urlpatterns)})

    def test_send_message_persisted(self):
        async def _test():
            app = self._get_application()
            token = await access_token_str(self.user_a)
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            await comm.connect()
            await comm.receive_json_from()  # history
            await comm.send_json_to({"type": "chat_message", "content": "Hello!"})
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "chat_message")
            self.assertEqual(response["message"]["content"], "Hello!")
            await comm.disconnect()
        async_to_sync(_test)()
        self.assertTrue(Message.objects.filter(expense=self.expense, content="Hello!").exists())

    def test_message_broadcast_to_second_connection(self):
        async def _test():
            app = self._get_application()
            token_a = await access_token_str(self.user_a)
            token_b = await access_token_str(self.user_b)

            comm_a = WebsocketCommunicator(app, ws_url(self.expense.id, token_a))
            comm_b = WebsocketCommunicator(app, ws_url(self.expense.id, token_b))

            await comm_a.connect()
            await comm_b.connect()
            await comm_a.receive_json_from()  # a history
            await comm_b.receive_json_from()  # b history

            await comm_a.send_json_to({"type": "chat_message", "content": "Broadcast!"})

            resp_a = await comm_a.receive_json_from()
            resp_b = await comm_b.receive_json_from()

            self.assertEqual(resp_a["message"]["content"], "Broadcast!")
            self.assertEqual(resp_b["message"]["content"], "Broadcast!")
            await comm_a.disconnect()
            await comm_b.disconnect()
        async_to_sync(_test)()

    def test_empty_message_not_sent(self):
        async def _test():
            app = self._get_application()
            token = await access_token_str(self.user_a)
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            await comm.connect()
            await comm.receive_json_from()  # history
            await comm.send_json_to({"type": "chat_message", "content": "   "})
            # Should not receive anything (no message persisted)
            self.assertTrue(await comm.receive_nothing(timeout=0.2))
            await comm.disconnect()
        async_to_sync(_test)()
        self.assertFalse(Message.objects.filter(expense=self.expense).exists())

    def test_delete_message_by_sender(self):
        msg = mk_message(self.expense, self.user_a, "To delete")

        async def _test():
            app = self._get_application()
            token = await access_token_str(self.user_a)
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token))
            await comm.connect()
            await comm.receive_json_from()  # history
            await comm.send_json_to({"type": "delete_message", "message_id": msg.id})
            response = await comm.receive_json_from()
            self.assertEqual(response["type"], "message_deleted")
            self.assertEqual(response["message_id"], msg.id)
            await comm.disconnect()
        async_to_sync(_test)()
        msg.refresh_from_db()
        self.assertTrue(msg.is_deleted)

    def test_delete_by_non_sender_no_broadcast(self):
        msg = mk_message(self.expense, self.user_a, "Only a can delete")

        async def _test():
            app = self._get_application()
            token_b = await access_token_str(self.user_b)
            comm = WebsocketCommunicator(app, ws_url(self.expense.id, token_b))
            await comm.connect()
            await comm.receive_json_from()  # history
            await comm.send_json_to({"type": "delete_message", "message_id": msg.id})
            self.assertTrue(await comm.receive_nothing(timeout=0.2))
            await comm.disconnect()
        async_to_sync(_test)()
        msg.refresh_from_db()
        self.assertFalse(msg.is_deleted)

    def test_cross_expense_isolation(self):
        """Message sent to expense 1 must not reach consumer connected to expense 2."""
        expense2 = mk_expense(self.group, self.user_a)

        async def _test():
            app = self._get_application()
            token_a = await access_token_str(self.user_a)

            comm1 = WebsocketCommunicator(app, ws_url(self.expense.id, token_a))
            comm2 = WebsocketCommunicator(app, ws_url(expense2.id, token_a))

            await comm1.connect()
            await comm2.connect()
            await comm1.receive_json_from()  # history
            await comm2.receive_json_from()  # history

            await comm1.send_json_to({"type": "chat_message", "content": "For exp1 only"})
            await comm1.receive_json_from()  # comm1 receives own message

            # comm2 must NOT receive anything
            self.assertTrue(await comm2.receive_nothing(timeout=0.2))
            await comm1.disconnect()
            await comm2.disconnect()
        async_to_sync(_test)()
