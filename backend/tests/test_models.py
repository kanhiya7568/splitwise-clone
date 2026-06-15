"""
Module 3 — Model Tests.

Tests model creation, string representation, constraints, soft-delete helpers,
and relationship integrity. Uses Django's test DB (SQLite in local settings).

Run with:
    python manage.py test tests.test_models
or:
    pytest tests/test_models.py -v
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.groups.models import Group, GroupInvitation, GroupMembership
from apps.expenses.models import Expense, ExpenseSplit
from apps.balances.models import Balance
from apps.settlements.models import Settlement
from apps.chat.models import Message


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_user(email="u@example.com", **kw) -> User:
    return User.objects.create_user(
        email=email, password="Pass1word", first_name="Test", last_name="User", **kw
    )


def make_group(creator=None, name="Test Group") -> Group:
    if creator is None:
        creator = make_user(f"creator-{name}@example.com")
    return Group.objects.create(name=name, created_by=creator)


def make_membership(group, user, role=GroupMembership.ROLE_MEMBER) -> GroupMembership:
    return GroupMembership.objects.create(group=group, user=user, role=role)


def make_expense(group, paid_by, amount="100.00", description="Dinner") -> Expense:
    return Expense.objects.create(
        group=group,
        paid_by=paid_by,
        created_by=paid_by,
        description=description,
        amount=Decimal(amount),
        expense_date=date.today(),
        split_type=Expense.SPLIT_EQUAL,
    )


# ─────────────────────────────────────────────────────────────────────────────
# User Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class UserModelTests(TestCase):
    def test_create_user(self):
        u = make_user("a@b.com")
        self.assertEqual(u.email, "a@b.com")
        self.assertTrue(u.is_active)
        self.assertFalse(u.is_staff)

    def test_str(self):
        u = make_user("x@y.com")
        self.assertEqual(str(u), "x@y.com")

    def test_get_full_name(self):
        u = User.objects.create_user(
            email="f@g.com", password="Pass1", first_name="Aarav", last_name="Singh"
        )
        self.assertEqual(u.get_full_name(), "Aarav Singh")

    def test_email_unique(self):
        make_user("dup@example.com")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_user("dup@example.com")

    def test_password_is_hashed(self):
        u = make_user("hash@example.com")
        self.assertNotEqual(u.password, "Pass1word")
        self.assertTrue(u.password.startswith("pbkdf2_"))

    def test_db_table(self):
        self.assertEqual(User._meta.db_table, "users")


# ─────────────────────────────────────────────────────────────────────────────
# Group Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class GroupModelTests(TestCase):
    def setUp(self):
        self.creator = make_user("creator@example.com")
        self.group = make_group(self.creator, "Holiday Trip")

    def test_create_group(self):
        self.assertEqual(self.group.name, "Holiday Trip")
        self.assertFalse(self.group.is_deleted)

    def test_str(self):
        self.assertEqual(str(self.group), "Holiday Trip")

    def test_soft_delete(self):
        self.group.soft_delete()
        self.group.refresh_from_db()
        self.assertTrue(self.group.is_deleted)

    def test_db_table(self):
        self.assertEqual(Group._meta.db_table, "groups")

    def test_created_by_relation(self):
        self.assertEqual(self.group.created_by, self.creator)


# ─────────────────────────────────────────────────────────────────────────────
# GroupMembership Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class GroupMembershipTests(TestCase):
    def setUp(self):
        self.creator = make_user("owner@example.com")
        self.member = make_user("member@example.com")
        self.group = make_group(self.creator)
        self.membership = make_membership(self.group, self.member)

    def test_create_membership(self):
        self.assertTrue(self.membership.is_active)
        self.assertEqual(self.membership.role, GroupMembership.ROLE_MEMBER)
        self.assertIsNone(self.membership.left_at)

    def test_str(self):
        s = str(self.membership)
        self.assertIn("member@example.com", s)
        self.assertIn("member", s)

    def test_unique_constraint_per_group_user(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GroupMembership.objects.create(group=self.group, user=self.member)

    def test_deactivate(self):
        self.membership.deactivate()
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.is_active)
        self.assertIsNotNone(self.membership.left_at)

    def test_admin_role(self):
        admin_m = make_membership(self.group, self.creator, role=GroupMembership.ROLE_ADMIN)
        self.assertEqual(admin_m.role, GroupMembership.ROLE_ADMIN)


# ─────────────────────────────────────────────────────────────────────────────
# GroupInvitation Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class GroupInvitationTests(TestCase):
    def setUp(self):
        self.creator = make_user("inv_creator@example.com")
        self.group = make_group(self.creator)

    def _make_invite(self, email="invite@example.com", status="pending"):
        return GroupInvitation.objects.create(
            group=self.group,
            email=email,
            invited_by=self.creator,
            status=status,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_create_invitation(self):
        inv = self._make_invite()
        self.assertEqual(inv.status, GroupInvitation.STATUS_PENDING)
        self.assertFalse(inv.is_expired)

    def test_str(self):
        inv = self._make_invite()
        self.assertIn("invite@example.com", str(inv))

    def test_duplicate_pending_raises(self):
        self._make_invite("dup@example.com")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_invite("dup@example.com")

    def test_second_invite_allowed_after_accepted(self):
        """Accepted invite should not block a new pending invite."""
        self._make_invite("re@example.com", status="accepted")
        inv2 = self._make_invite("re@example.com", status="pending")
        self.assertEqual(inv2.status, "pending")

    def test_is_expired_property(self):
        inv = GroupInvitation.objects.create(
            group=self.group,
            email="exp@example.com",
            invited_by=self.creator,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(inv.is_expired)


# ─────────────────────────────────────────────────────────────────────────────
# Expense Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseModelTests(TestCase):
    def setUp(self):
        self.user = make_user("expense_user@example.com")
        self.group = make_group(self.user)
        self.expense = make_expense(self.group, self.user)

    def test_create_expense(self):
        self.assertEqual(self.expense.amount, Decimal("100.00"))
        self.assertFalse(self.expense.is_deleted)
        self.assertEqual(self.expense.split_type, Expense.SPLIT_EQUAL)

    def test_str(self):
        self.assertIn("Dinner", str(self.expense))
        self.assertIn("100", str(self.expense))

    def test_soft_delete(self):
        self.expense.soft_delete()
        self.expense.refresh_from_db()
        self.assertTrue(self.expense.is_deleted)

    def test_default_category(self):
        self.assertEqual(self.expense.category, Expense.CATEGORY_GENERAL)

    def test_db_table(self):
        self.assertEqual(Expense._meta.db_table, "expenses")

    def test_amount_zero_rejected(self):
        """CheckConstraint: amount must be > 0."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Expense.objects.create(
                    group=self.group, paid_by=self.user, created_by=self.user,
                    description="Bad", amount=Decimal("0.00"),
                    expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                )

    def test_amount_negative_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Expense.objects.create(
                    group=self.group, paid_by=self.user, created_by=self.user,
                    description="Bad", amount=Decimal("-10.00"),
                    expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                )


# ─────────────────────────────────────────────────────────────────────────────
# ExpenseSplit Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseSplitTests(TestCase):
    def setUp(self):
        self.user1 = make_user("split_u1@example.com")
        self.user2 = make_user("split_u2@example.com")
        self.group = make_group(self.user1)
        self.expense = make_expense(self.group, self.user1, "100.00")

    def _make_split(self, user, amount="50.00"):
        return ExpenseSplit.objects.create(
            expense=self.expense, user=user, amount=Decimal(amount)
        )

    def test_create_split(self):
        s = self._make_split(self.user1)
        self.assertEqual(s.amount, Decimal("50.00"))

    def test_str(self):
        s = self._make_split(self.user1)
        self.assertIn("owes", str(s))

    def test_unique_per_expense_user(self):
        self._make_split(self.user1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_split(self.user1)

    def test_zero_amount_allowed(self):
        """0-share participants may have amount=0."""
        s = self._make_split(self.user2, "0.00")
        self.assertEqual(s.amount, Decimal("0.00"))

    def test_negative_amount_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_split(self.user2, "-1.00")

    def test_percentage_and_shares_nullable(self):
        s = self._make_split(self.user1)
        self.assertIsNone(s.percentage)
        self.assertIsNone(s.shares)


# ─────────────────────────────────────────────────────────────────────────────
# Balance Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class BalanceModelTests(TestCase):
    def setUp(self):
        # Ensure user1.id < user2.id by creating in order
        self.user1 = make_user("bal_u1@example.com")
        self.user2 = make_user("bal_u2@example.com")
        # Guarantee ordering
        if self.user1.id > self.user2.id:
            self.user1, self.user2 = self.user2, self.user1
        self.group = make_group(self.user1)

    def _make_balance(self, amount="50.00"):
        return Balance.objects.create(
            group=self.group,
            user1=self.user1,
            user2=self.user2,
            net_amount=Decimal(amount),
        )

    def test_create_balance(self):
        b = self._make_balance()
        self.assertEqual(b.net_amount, Decimal("50.00"))

    def test_str(self):
        b = self._make_balance()
        self.assertIn("↔", str(b))

    def test_unique_pair_per_group(self):
        self._make_balance()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_balance("10.00")

    def test_user1_lt_user2_constraint(self):
        """DB must reject user1_id >= user2_id."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Balance.objects.create(
                    group=self.group,
                    user1=self.user2,  # wrong order
                    user2=self.user1,
                    net_amount=Decimal("10.00"),
                )

    def test_db_table(self):
        self.assertEqual(Balance._meta.db_table, "balances")

    def test_net_amount_can_be_zero(self):
        b = self._make_balance("0.00")
        self.assertEqual(b.net_amount, Decimal("0.00"))

    def test_net_amount_can_be_negative(self):
        """Negative means user1 owes user2."""
        b = self._make_balance("-30.00")
        self.assertEqual(b.net_amount, Decimal("-30.00"))


# ─────────────────────────────────────────────────────────────────────────────
# Settlement Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class SettlementModelTests(TestCase):
    def setUp(self):
        self.payer = make_user("payer@example.com")
        self.receiver = make_user("receiver@example.com")
        self.group = make_group(self.payer)

    def _make_settlement(self, amount="50.00", payer=None, receiver=None):
        return Settlement.objects.create(
            group=self.group,
            payer=payer or self.payer,
            receiver=receiver or self.receiver,
            created_by=payer or self.payer,
            amount=Decimal(amount),
        )

    def test_create_settlement(self):
        s = self._make_settlement()
        self.assertEqual(s.amount, Decimal("50.00"))
        self.assertFalse(s.is_deleted)

    def test_str(self):
        s = self._make_settlement()
        self.assertIn("→", str(s))

    def test_soft_delete(self):
        s = self._make_settlement()
        s.soft_delete()
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)

    def test_amount_zero_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_settlement("0.00")

    def test_amount_negative_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_settlement("-10.00")

    def test_payer_equals_receiver_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_settlement(payer=self.payer, receiver=self.payer)

    def test_db_table(self):
        self.assertEqual(Settlement._meta.db_table, "settlements")


# ─────────────────────────────────────────────────────────────────────────────
# Message Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class MessageModelTests(TestCase):
    def setUp(self):
        self.user = make_user("chat_user@example.com")
        self.group = make_group(self.user)
        self.expense = make_expense(self.group, self.user)

    def _make_message(self, content="Hello!"):
        return Message.objects.create(
            expense=self.expense, sender=self.user, content=content
        )

    def test_create_message(self):
        m = self._make_message()
        self.assertEqual(m.content, "Hello!")
        self.assertFalse(m.is_deleted)

    def test_str_short_content(self):
        m = self._make_message("Hi")
        self.assertIn("Hi", str(m))

    def test_str_long_content_truncated(self):
        m = self._make_message("A" * 100)
        self.assertIn("...", str(m))

    def test_soft_delete(self):
        m = self._make_message()
        m.soft_delete()
        m.refresh_from_db()
        self.assertTrue(m.is_deleted)
        # Content preserved in DB after soft delete
        self.assertEqual(m.content, "Hello!")

    def test_ordering_chronological(self):
        m1 = self._make_message("First")
        m2 = self._make_message("Second")
        messages = list(Message.objects.filter(expense=self.expense))
        self.assertEqual(messages[0].content, "First")
        self.assertEqual(messages[1].content, "Second")

    def test_db_table(self):
        self.assertEqual(Message._meta.db_table, "messages")

    def test_expense_cascade_deletes_messages(self):
        """Hard-deleting an expense must remove its messages."""
        m = self._make_message()
        msg_id = m.id
        self.expense.delete()
        self.assertFalse(Message.objects.filter(id=msg_id).exists())
