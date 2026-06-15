"""
Settlement API tests — Module 8.

Run: python manage.py test apps.settlements
"""

from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.balances.models import Balance
from apps.expenses.models import Expense, ExpenseSplit
from apps.balances.services import apply_expense_to_balances
from apps.groups.models import Group, GroupMembership
from apps.settlements.models import Settlement
from apps.settlements.services import SettlementServiceError
from apps.settlements import services
from apps.users.models import User

D = Decimal


# ─── helpers ──────────────────────────────────────────────────────────────────

def mk_user(email):
    return User.objects.create_user(
        email=email, password="Pass1word", first_name="T", last_name="U"
    )


def auth(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


def mk_group(creator):
    g = Group.objects.create(name="G", created_by=creator)
    GroupMembership.objects.create(group=g, user=creator, role=GroupMembership.ROLE_ADMIN)
    return g


def add_member(group, user):
    GroupMembership.objects.create(group=group, user=user, role=GroupMembership.ROLE_MEMBER)


def mk_balance(group, u1, u2, amount_str):
    """Create a direct balance row (u1 is owed amount by u2)."""
    uid1, uid2 = min(u1.id, u2.id), max(u1.id, u2.id)
    net = D(amount_str) if u1.id < u2.id else -D(amount_str)
    return Balance.objects.create(group=group, user1_id=uid1, user2_id=uid2, net_amount=net)


def get_net(group, u1, u2):
    uid1, uid2 = min(u1.id, u2.id), max(u1.id, u2.id)
    b = Balance.objects.filter(group=group, user1_id=uid1, user2_id=uid2).first()
    return b.net_amount if b else D("0.00")


def mk_expense_balance(group, payer, debtor, amount_str):
    """Create expense and apply balance in one call."""
    exp = Expense.objects.create(
        group=group, paid_by=payer, created_by=payer,
        description="X", amount=D(amount_str),
        category=Expense.CATEGORY_FOOD, expense_date=date.today(),
        split_type=Expense.SPLIT_EQUAL,
    )
    splits = [ExpenseSplit.objects.create(expense=exp, user=debtor, amount=D(amount_str))]
    apply_expense_to_balances(exp, splits)
    return exp


# ─── Service layer tests (no HTTP) ───────────────────────────────────────────

class CreateSettlementServiceTests(APITestCase):
    def setUp(self):
        self.payer = mk_user("sp@x.com")
        self.receiver = mk_user("sr@x.com")
        self.outsider = mk_user("so@x.com")
        self.group = mk_group(self.payer)
        add_member(self.group, self.receiver)

    def test_create_returns_settlement(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("50.00")
        )
        self.assertIsNotNone(s.pk)
        self.assertFalse(s.is_deleted)

    def test_balance_updated_after_create(self):
        mk_balance(self.group, self.receiver, self.payer, "80.00")
        before = abs(get_net(self.group, self.payer, self.receiver))
        services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("30.00")
        )
        after = abs(get_net(self.group, self.payer, self.receiver))
        self.assertEqual(before - after, D("30.00"))

    def test_full_settlement_deletes_balance_row(self):
        mk_balance(self.group, self.receiver, self.payer, "50.00")
        services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("50.00")
        )
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)

    def test_payer_equals_receiver_raises(self):
        with self.assertRaises(SettlementServiceError):
            services.create_settlement(
                group=self.group, created_by=self.payer,
                payer_id=self.payer.id, receiver_id=self.payer.id, amount=D("50.00")
            )

    def test_outsider_payer_raises(self):
        with self.assertRaises(SettlementServiceError):
            services.create_settlement(
                group=self.group, created_by=self.payer,
                payer_id=self.outsider.id, receiver_id=self.receiver.id, amount=D("50.00")
            )

    def test_outsider_created_by_raises(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.create_settlement(
                group=self.group, created_by=self.outsider,
                payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("50.00")
            )

    def test_partial_settlement_allowed(self):
        mk_balance(self.group, self.receiver, self.payer, "100.00")
        services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        self.assertEqual(
            abs(get_net(self.group, self.payer, self.receiver)), D("60.00")
        )

    def test_note_stored(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id,
            amount=D("50.00"), note="For last dinner"
        )
        self.assertEqual(s.note, "For last dinner")


class UpdateSettlementServiceTests(APITestCase):
    def setUp(self):
        self.payer = mk_user("up@x.com")
        self.receiver = mk_user("ur@x.com")
        self.third = mk_user("ut@x.com")
        self.group = mk_group(self.payer)
        add_member(self.group, self.receiver)
        add_member(self.group, self.third)
        mk_balance(self.group, self.receiver, self.payer, "100.00")
        self.settlement = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )

    def test_payer_can_edit(self):
        s = services.update_settlement(self.settlement, self.payer, amount=D("60.00"))
        self.assertEqual(s.amount, D("60.00"))

    def test_receiver_can_edit(self):
        s = services.update_settlement(self.settlement, self.receiver, note="Updated note")
        self.assertEqual(s.note, "Updated note")

    def test_third_party_cannot_edit(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.update_settlement(self.settlement, self.third, amount=D("10.00"))

    def test_balance_correctly_updated_after_edit(self):
        before_balance = abs(get_net(self.group, self.payer, self.receiver))
        # Change from 40 to 60
        services.update_settlement(self.settlement, self.payer, amount=D("60.00"))
        after_balance = abs(get_net(self.group, self.payer, self.receiver))
        self.assertEqual(before_balance - after_balance, D("20.00"))

    def test_edit_deleted_settlement_raises(self):
        services.delete_settlement(self.settlement, self.payer)
        with self.assertRaises(SettlementServiceError):
            services.update_settlement(self.settlement, self.payer, amount=D("10.00"))


class DeleteSettlementServiceTests(APITestCase):
    def setUp(self):
        self.payer = mk_user("dp@x.com")
        self.receiver = mk_user("dr@x.com")
        self.third = mk_user("dt@x.com")
        self.group = mk_group(self.payer)
        add_member(self.group, self.receiver)
        add_member(self.group, self.third)
        mk_balance(self.group, self.receiver, self.payer, "80.00")
        self.settlement = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("50.00")
        )

    def test_payer_can_delete(self):
        services.delete_settlement(self.settlement, self.payer)
        self.settlement.refresh_from_db()
        self.assertTrue(self.settlement.is_deleted)

    def test_receiver_can_delete(self):
        services.delete_settlement(self.settlement, self.receiver)
        self.settlement.refresh_from_db()
        self.assertTrue(self.settlement.is_deleted)

    def test_third_cannot_delete(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.delete_settlement(self.settlement, self.third)

    def test_balance_restored_after_delete(self):
        before = abs(get_net(self.group, self.payer, self.receiver))
        services.delete_settlement(self.settlement, self.payer)
        after = abs(get_net(self.group, self.payer, self.receiver))
        self.assertEqual(after - before, D("50.00"))

    def test_record_preserved_after_soft_delete(self):
        services.delete_settlement(self.settlement, self.payer)
        self.assertTrue(Settlement.objects.filter(pk=self.settlement.pk).exists())

    def test_double_delete_raises(self):
        services.delete_settlement(self.settlement, self.payer)
        with self.assertRaises(SettlementServiceError):
            services.delete_settlement(self.settlement, self.payer)


class HistoryServiceTests(APITestCase):
    def setUp(self):
        self.payer = mk_user("hp@x.com")
        self.receiver = mk_user("hr@x.com")
        self.outsider = mk_user("ho@x.com")
        self.group = mk_group(self.payer)
        add_member(self.group, self.receiver)

    def test_member_can_view_history(self):
        qs = services.get_settlement_history(self.group, self.receiver)
        self.assertIsNotNone(qs)

    def test_outsider_cannot_view_history(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            services.get_settlement_history(self.group, self.outsider)

    def test_deleted_excluded_by_default(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("10.00")
        )
        services.delete_settlement(s, self.payer)
        qs = services.get_settlement_history(self.group, self.payer)
        self.assertNotIn(s.pk, qs.values_list("id", flat=True))

    def test_deleted_included_with_flag(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("10.00")
        )
        services.delete_settlement(s, self.payer)
        qs = services.get_settlement_history(self.group, self.payer, include_deleted=True)
        self.assertIn(s.pk, qs.values_list("id", flat=True))

    def test_ordering_newest_first(self):
        for amt in ["10.00", "20.00", "30.00"]:
            services.create_settlement(
                group=self.group, created_by=self.payer,
                payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D(amt)
            )
        qs = list(services.get_settlement_history(self.group, self.payer))
        dates = [s.created_at for s in qs]
        self.assertEqual(dates, sorted(dates, reverse=True))


# ─── API (HTTP) tests ─────────────────────────────────────────────────────────

class SettlementAPITests(APITestCase):
    def setUp(self):
        self.payer = mk_user("ap@x.com")
        self.receiver = mk_user("ar@x.com")
        self.outsider = mk_user("ao@x.com")
        self.group = mk_group(self.payer)
        add_member(self.group, self.receiver)
        self.list_url = reverse("settlement_list_create", kwargs={"gid": self.group.pk})

    def test_create_settlement_201(self):
        r = self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "50.00"},
            format="json", **auth(self.payer)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_create_returns_settlement_data(self):
        r = self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "50.00"},
            format="json", **auth(self.payer)
        )
        self.assertIn("id", r.json())
        self.assertIn("amount", r.json())

    def test_payer_equals_receiver_400(self):
        r = self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.payer.id, "amount": "50.00"},
            format="json", **auth(self.payer)
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outsider_cannot_create_403(self):
        r = self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "50.00"},
            format="json", **auth(self.outsider)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_401(self):
        r = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_zero_amount_400(self):
        r = self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "0.00"},
            format="json", **auth(self.payer)
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_settlements_200(self):
        self.client.post(
            self.list_url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "20.00"},
            format="json", **auth(self.payer)
        )
        r = self.client.get(self.list_url, **auth(self.payer))
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["count"], 1)

    def test_outsider_cannot_list_403(self):
        r = self.client.get(self.list_url, **auth(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_edit_settlement_200(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        url = reverse("settlement_update", kwargs={"gid": self.group.pk, "sid": s.pk})
        r = self.client.patch(url, {"amount": "60.00"}, format="json", **auth(self.payer))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(D(r.json()["amount"]), D("60.00"))

    def test_third_party_edit_403(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        url = reverse("settlement_update", kwargs={"gid": self.group.pk, "sid": s.pk})
        r = self.client.patch(url, {"amount": "10.00"}, format="json", **auth(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_settlement_200(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        url = reverse("settlement_delete", kwargs={"gid": self.group.pk, "sid": s.pk})
        r = self.client.delete(url, **auth(self.payer))
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)

    def test_third_party_delete_403(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        url = reverse("settlement_delete", kwargs={"gid": self.group.pk, "sid": s.pk})
        r = self.client.delete(url, **auth(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_soft_deleted_not_in_list(self):
        s = services.create_settlement(
            group=self.group, created_by=self.payer,
            payer_id=self.payer.id, receiver_id=self.receiver.id, amount=D("40.00")
        )
        services.delete_settlement(s, self.payer)
        r = self.client.get(self.list_url, **auth(self.payer))
        ids = [item["id"] for item in r.json()["results"]]
        self.assertNotIn(s.pk, ids)

    def test_nonexistent_group_404(self):
        url = reverse("settlement_list_create", kwargs={"gid": 99999})
        r = self.client.post(
            url,
            {"payer_id": self.payer.id, "receiver_id": self.receiver.id, "amount": "10.00"},
            format="json", **auth(self.payer)
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


# ─── Decimal precision and cross-group isolation ───────────────────────────────

class DecimalAndIsolationTests(APITestCase):
    def setUp(self):
        self.u1 = mk_user("di1@x.com")
        self.u2 = mk_user("di2@x.com")
        self.group = mk_group(self.u1)
        add_member(self.group, self.u2)

    def test_cent_precision_preserved(self):
        s = services.create_settlement(
            group=self.group, created_by=self.u1,
            payer_id=self.u1.id, receiver_id=self.u2.id, amount=D("0.01")
        )
        self.assertEqual(s.amount, D("0.01"))

    def test_cross_group_balance_not_affected(self):
        other_user = mk_user("di_other@x.com")
        group2 = mk_group(other_user)
        add_member(group2, self.u2)

        mk_balance(group2, other_user, self.u2, "200.00")
        bal_before = abs(get_net(group2, other_user, self.u2))

        mk_balance(self.group, self.u2, self.u1, "50.00")
        services.create_settlement(
            group=self.group, created_by=self.u1,
            payer_id=self.u1.id, receiver_id=self.u2.id, amount=D("50.00")
        )

        bal_after = abs(get_net(group2, other_user, self.u2))
        self.assertEqual(bal_before, bal_after)
