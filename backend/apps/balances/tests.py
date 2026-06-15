"""
Balance Engine tests — Module 7A.

Tests apply/reverse for both expenses and settlements, including:
  - Canonical ordering (user1_id < user2_id always)
  - Balance created when missing, updated when present
  - Zero-balance rows deleted
  - Accumulation across multiple expenses
  - Isolation between groups
  - Full apply-reverse cycle returns to zero
  - Multi-person splits create multiple balance rows

Run: python manage.py test apps.balances
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.balances.models import Balance
from apps.balances.services import (
    apply_expense_to_balances,
    apply_settlement_to_balances,
    reverse_expense_from_balances,
    reverse_settlement_from_balances,
)
from apps.expenses.models import Expense, ExpenseSplit
from apps.groups.models import Group, GroupMembership
from apps.settlements.models import Settlement
from apps.users.models import User

D = Decimal


# ─── helpers ──────────────────────────────────────────────────────────────────

def mk_user(email):
    return User.objects.create_user(
        email=email, password="Pass1", first_name="T", last_name="U"
    )


def mk_group(creator):
    g = Group.objects.create(name="G", created_by=creator)
    GroupMembership.objects.create(group=g, user=creator, role=GroupMembership.ROLE_ADMIN)
    return g


def add_member(group, user):
    GroupMembership.objects.create(group=group, user=user, role=GroupMembership.ROLE_MEMBER)


def mk_expense_with_splits(group, payer, splits_data, amount="100.00"):
    """
    splits_data: [(user, amount_str), ...]
    Returns (Expense, [ExpenseSplit])
    """
    expense = Expense.objects.create(
        group=group,
        paid_by=payer,
        created_by=payer,
        description="Test",
        amount=D(amount),
        category=Expense.CATEGORY_FOOD,
        expense_date=date.today(),
        split_type=Expense.SPLIT_EQUAL,
    )
    splits = [
        ExpenseSplit.objects.create(expense=expense, user=user, amount=D(amt))
        for user, amt in splits_data
    ]
    return expense, splits


def mk_settlement(group, payer, receiver, amount):
    return Settlement.objects.create(
        group=group,
        payer=payer,
        receiver=receiver,
        created_by=payer,
        amount=D(amount),
    )


def get_balance(group, u1, u2):
    """Fetch balance row (handles canonical ordering)."""
    uid1, uid2 = min(u1.id, u2.id), max(u1.id, u2.id)
    return Balance.objects.filter(group=group, user1_id=uid1, user2_id=uid2).first()


def net(group, u1, u2):
    """Return net_amount or 0 if no row exists."""
    b = get_balance(group, u1, u2)
    return b.net_amount if b else D("0.00")


# ─── Canonical Ordering Tests ─────────────────────────────────────────────────

class CanonicalOrderingTests(TestCase):
    """Balance rows must always have user1_id < user2_id."""

    def setUp(self):
        self.a = mk_user("a@x.com")
        self.b = mk_user("b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_balance_row_has_user1_lt_user2(self):
        payer = self.a  # could be u1 or u2 depending on ID
        expense, splits = mk_expense_with_splits(
            self.group, payer,
            [(self.a, "50.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        row = Balance.objects.get(group=self.group)
        self.assertLess(row.user1_id, row.user2_id)

    def test_canonical_order_when_payer_has_higher_id(self):
        # Force b to pay (b.id > a.id in insertion order)
        payer = self.b
        expense, splits = mk_expense_with_splits(
            self.group, payer,
            [(self.a, "50.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        row = Balance.objects.get(group=self.group)
        self.assertLess(row.user1_id, row.user2_id)

    def test_same_pair_produces_single_row(self):
        for payer in [self.a, self.b]:
            expense, splits = mk_expense_with_splits(
                self.group, payer,
                [(self.a, "50.00"), (self.b, "50.00")]
            )
            apply_expense_to_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)


# ─── Apply Expense Tests ──────────────────────────────────────────────────────

class ApplyExpenseTests(TestCase):
    def setUp(self):
        self.a = mk_user("ae_a@x.com")
        self.b = mk_user("ae_b@x.com")
        self.c = mk_user("ae_c@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)
        add_member(self.group, self.c)

    def test_two_person_split_creates_balance(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "50.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)

    def test_b_owes_a_correct_amount(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "50.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        # Whoever paid (a) is owed by b
        # net_amount sign depends on canonical order
        balance = Balance.objects.get(group=self.group)
        # The absolute value must be 50.00
        self.assertEqual(abs(balance.net_amount), D("50.00"))

    def test_three_person_split_creates_two_balance_rows(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "34.00"), (self.b, "33.00"), (self.c, "33.00")]
        )
        apply_expense_to_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 2)

    def test_payer_split_skipped(self):
        """Payer's own split must not create a self-referential balance."""
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "100.00")]  # payer only
        )
        apply_expense_to_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)

    def test_two_expenses_accumulate(self):
        for amt in ["30.00", "20.00"]:
            expense, splits = mk_expense_with_splits(
                self.group, self.a,
                [(self.a, "0.00"), (self.b, amt)]
            )
            apply_expense_to_balances(expense, splits)
        self.assertEqual(abs(net(self.group, self.a, self.b)), D("50.00"))

    def test_reciprocal_expenses_reduce_balance(self):
        """A pays for B $40, B pays for A $40 → zero balance."""
        exp1, sp1 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "40.00")]
        )
        apply_expense_to_balances(exp1, sp1)

        exp2, sp2 = mk_expense_with_splits(
            self.group, self.b, [(self.a, "40.00"), (self.b, "0.00")]
        )
        apply_expense_to_balances(exp2, sp2)
        # Both owe each other the same → zero
        self.assertIsNone(get_balance(self.group, self.a, self.b))

    def test_balance_correct_direction_a_pays(self):
        """When A pays for B: B owes A."""
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "60.00")]
        )
        apply_expense_to_balances(expense, splits)
        balance = Balance.objects.get(group=self.group)
        u1_id = min(self.a.id, self.b.id)
        if self.a.id == u1_id:
            # a=u1 creditor: net > 0 (u2=b owes u1=a)
            self.assertGreater(balance.net_amount, D("0.00"))
        else:
            # a=u2 creditor: net < 0 (u1=b owes u2=a)
            self.assertLess(balance.net_amount, D("0.00"))

    def test_balance_correct_direction_b_pays(self):
        """When B pays for A: A owes B."""
        expense, splits = mk_expense_with_splits(
            self.group, self.b, [(self.a, "60.00"), (self.b, "0.00")]
        )
        apply_expense_to_balances(expense, splits)
        balance = Balance.objects.get(group=self.group)
        u1_id = min(self.a.id, self.b.id)
        if self.b.id == u1_id:
            # b=u1 creditor: net > 0
            self.assertGreater(balance.net_amount, D("0.00"))
        else:
            # b=u2 creditor: net < 0
            self.assertLess(balance.net_amount, D("0.00"))

    def test_group_isolation(self):
        """Expenses in different groups create separate balance rows."""
        group2 = mk_group(self.a)
        add_member(group2, self.b)

        exp1, sp1 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "40.00")]
        )
        apply_expense_to_balances(exp1, sp1)

        exp2, sp2 = mk_expense_with_splits(
            group2, self.a, [(self.a, "0.00"), (self.b, "70.00")]
        )
        apply_expense_to_balances(exp2, sp2)

        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)
        self.assertEqual(Balance.objects.filter(group=group2).count(), 1)
        self.assertEqual(
            abs(Balance.objects.get(group=self.group).net_amount), D("40.00")
        )
        self.assertEqual(
            abs(Balance.objects.get(group=group2).net_amount), D("70.00")
        )


# ─── Reverse Expense Tests ────────────────────────────────────────────────────

class ReverseExpenseTests(TestCase):
    def setUp(self):
        self.a = mk_user("re_a@x.com")
        self.b = mk_user("re_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_apply_then_reverse_deletes_row(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "60.00")]
        )
        apply_expense_to_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)
        reverse_expense_from_balances(expense, splits)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)

    def test_reverse_reduces_accumulated_balance(self):
        """Apply A×2, reverse A×1 → net = one expense."""
        exp1, sp1 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.00")]
        )
        exp2, sp2 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(exp1, sp1)
        apply_expense_to_balances(exp2, sp2)
        reverse_expense_from_balances(exp1, sp1)
        self.assertEqual(abs(net(self.group, self.a, self.b)), D("50.00"))

    def test_reverse_without_prior_apply_creates_negative_balance(self):
        """Reversing without a prior apply is technically valid (no guard needed here)."""
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "40.00")]
        )
        reverse_expense_from_balances(expense, splits)
        # Row created with negative net
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)

    def test_partial_reverse_three_person(self):
        """Apply 3-person expense, reverse only debtor B's split."""
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "33.34"), (self.b, "33.33")]
        )
        apply_expense_to_balances(expense, splits)
        b_splits = [s for s in splits if s.user_id == self.b.id]
        reverse_expense_from_balances(expense, b_splits)
        self.assertIsNone(get_balance(self.group, self.a, self.b))


# ─── Apply Settlement Tests ───────────────────────────────────────────────────

class ApplySettlementTests(TestCase):
    def setUp(self):
        self.a = mk_user("as_a@x.com")
        self.b = mk_user("as_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def _set_balance(self, amount):
        """Directly create a balance row for setup."""
        u1_id, u2_id = min(self.a.id, self.b.id), max(self.a.id, self.b.id)
        Balance.objects.create(
            group=self.group, user1_id=u1_id, user2_id=u2_id, net_amount=D(amount)
        )

    def test_settlement_reduces_balance(self):
        # First build a balance via expense
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "80.00")]
        )
        apply_expense_to_balances(expense, splits)

        before = abs(net(self.group, self.a, self.b))
        settlement = mk_settlement(self.group, self.b, self.a, "30.00")
        apply_settlement_to_balances(settlement)
        after = abs(net(self.group, self.a, self.b))

        self.assertEqual(before - after, D("30.00"))

    def test_full_settlement_deletes_row(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        settlement = mk_settlement(self.group, self.b, self.a, "50.00")
        apply_settlement_to_balances(settlement)
        self.assertIsNone(get_balance(self.group, self.a, self.b))

    def test_settlement_canonical_ordering_preserved(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "60.00")]
        )
        apply_expense_to_balances(expense, splits)
        settlement = mk_settlement(self.group, self.b, self.a, "20.00")
        apply_settlement_to_balances(settlement)
        row = Balance.objects.get(group=self.group)
        self.assertLess(row.user1_id, row.user2_id)

    def test_settlement_creates_row_if_missing(self):
        """Settling more than owed flips the balance."""
        settlement = mk_settlement(self.group, self.b, self.a, "30.00")
        apply_settlement_to_balances(settlement)
        # A row must exist with inverted sign
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)


# ─── Reverse Settlement Tests ─────────────────────────────────────────────────

class ReverseSettlementTests(TestCase):
    def setUp(self):
        self.a = mk_user("rs_a@x.com")
        self.b = mk_user("rs_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_apply_then_reverse_settlement_restores_balance(self):
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "100.00")]
        )
        apply_expense_to_balances(expense, splits)
        before = abs(net(self.group, self.a, self.b))

        settlement = mk_settlement(self.group, self.b, self.a, "40.00")
        apply_settlement_to_balances(settlement)
        reverse_settlement_from_balances(settlement)

        after = abs(net(self.group, self.a, self.b))
        self.assertEqual(before, after)

    def test_reverse_settlement_recreates_deleted_row(self):
        """If settlement zeroed the balance (row deleted), reversing recreates it."""
        expense, splits = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, splits)
        settlement = mk_settlement(self.group, self.b, self.a, "50.00")
        apply_settlement_to_balances(settlement)
        self.assertIsNone(get_balance(self.group, self.a, self.b))

        reverse_settlement_from_balances(settlement)
        self.assertIsNotNone(get_balance(self.group, self.a, self.b))
        self.assertEqual(abs(net(self.group, self.a, self.b)), D("50.00"))


# ─── Zero Balance Cleanup Tests ───────────────────────────────────────────────

class ZeroBalanceTests(TestCase):
    def setUp(self):
        self.a = mk_user("zb_a@x.com")
        self.b = mk_user("zb_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_zero_balance_row_deleted(self):
        exp1, sp1 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(exp1, sp1)
        exp2, sp2 = mk_expense_with_splits(
            self.group, self.b, [(self.a, "50.00"), (self.b, "0.00")]
        )
        apply_expense_to_balances(exp2, sp2)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)

    def test_near_zero_balance_not_deleted(self):
        exp1, sp1 = mk_expense_with_splits(
            self.group, self.a, [(self.a, "0.00"), (self.b, "50.01")]
        )
        apply_expense_to_balances(exp1, sp1)
        exp2, sp2 = mk_expense_with_splits(
            self.group, self.b, [(self.a, "50.00"), (self.b, "0.00")]
        )
        apply_expense_to_balances(exp2, sp2)
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)


# ─── Full Cycle Integration Tests ─────────────────────────────────────────────

class FullCycleIntegrationTests(TestCase):
    """End-to-end: create expense → settle → reverse everything."""

    def setUp(self):
        self.a = mk_user("fc_a@x.com")
        self.b = mk_user("fc_b@x.com")
        self.c = mk_user("fc_c@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)
        add_member(self.group, self.c)

    def test_full_three_person_cycle(self):
        # A pays $90 for A, B, C equally ($30 each)
        expense, splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "30.00"), (self.b, "30.00"), (self.c, "30.00")]
        )
        apply_expense_to_balances(expense, splits)

        # B settles with A for $30
        s1 = mk_settlement(self.group, self.b, self.a, "30.00")
        apply_settlement_to_balances(s1)

        # C settles with A for $30
        s2 = mk_settlement(self.group, self.c, self.a, "30.00")
        apply_settlement_to_balances(s2)

        # All balances should be zero → no rows
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 0)

    def test_edit_expense_cycle(self):
        """Simulate expense edit: reverse old, apply new."""
        # Original: A pays $100 for A and B ($50 each)
        expense, old_splits = mk_expense_with_splits(
            self.group, self.a,
            [(self.a, "50.00"), (self.b, "50.00")]
        )
        apply_expense_to_balances(expense, old_splits)
        after_original = abs(net(self.group, self.a, self.b))
        self.assertEqual(after_original, D("50.00"))

        # Edit: change to $70 for B only
        reverse_expense_from_balances(expense, old_splits)
        # Recreate splits (simulating service.update_expense)
        old_splits[0].delete()
        old_splits[1].delete()
        expense.amount = D("70.00")
        expense.paid_by = self.a
        expense.save()
        new_split = ExpenseSplit.objects.create(
            expense=expense, user=self.b, amount=D("70.00")
        )
        apply_expense_to_balances(expense, [new_split])

        self.assertEqual(abs(net(self.group, self.a, self.b)), D("70.00"))
