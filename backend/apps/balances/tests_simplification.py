"""
Debt simplification tests — Module 7B.

Tests simplify_debts() (pure function) and compute_net_balances_for_group() (DB).

Run: python manage.py test apps.balances.tests_simplification
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase

from apps.balances.models import Balance
from apps.balances.simplification import (
    compute_net_balances_for_group,
    get_simplified_debts_for_group,
    simplify_debts,
)
from apps.balances.services import apply_expense_to_balances
from apps.expenses.models import Expense, ExpenseSplit
from apps.groups.models import Group, GroupMembership
from apps.users.models import User

D = Decimal


# ─── helpers ──────────────────────────────────────────────────────────────────

def nb(user_id, amount):
    """Build a net_balance dict."""
    return {"user_id": user_id, "amount": D(str(amount))}


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


def set_balance(group, u1, u2, amount):
    """Directly insert a canonical balance row for test setup."""
    uid1 = min(u1.id, u2.id)
    uid2 = max(u1.id, u2.id)
    # Net amount sign: if u1 is user1 and u2 is user2, positive means u2 owes u1
    # We just want "u2 owes u1 amount"
    net = D(str(amount)) if u1.id < u2.id else -D(str(amount))
    Balance.objects.create(group=group, user1_id=uid1, user2_id=uid2, net_amount=net)


def total_settled(transactions):
    return sum(t["amount"] for t in transactions)


def verify_settled(net_balances, transactions):
    """
    Apply the output transactions to the net balances and verify all reach zero.
    Returns True if all balances are settled.
    """
    position = {e["user_id"]: e["amount"] for e in net_balances}
    for t in transactions:
        position[t["payer_id"]] += t["amount"]
        position[t["receiver_id"]] -= t["amount"]
    return all(abs(v) < D("0.01") for v in position.values())


# ─── Empty / Zero Input Tests ─────────────────────────────────────────────────

class EmptyInputTests(TestCase):
    def test_empty_list_returns_empty(self):
        self.assertEqual(simplify_debts([]), [])

    def test_all_zeros_returns_empty(self):
        result = simplify_debts([nb(1, "0.00"), nb(2, "0.00")])
        self.assertEqual(result, [])

    def test_single_creditor_no_debtor_raises(self):
        with self.assertRaises(ValueError):
            simplify_debts([nb(1, "50.00")])

    def test_single_debtor_no_creditor_raises(self):
        with self.assertRaises(ValueError):
            simplify_debts([nb(1, "-50.00")])


# ─── Zero-Sum Validation Tests ────────────────────────────────────────────────

class ZeroSumValidationTests(TestCase):
    def test_unbalanced_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            simplify_debts([nb(1, "100.00"), nb(2, "-90.00")])

    def test_balanced_input_does_not_raise(self):
        try:
            simplify_debts([nb(1, "50.00"), nb(2, "-50.00")])
        except ValueError:
            self.fail("simplify_debts raised ValueError on balanced input")

    def test_error_message_mentions_rebuild(self):
        with self.assertRaises(ValueError) as ctx:
            simplify_debts([nb(1, "10.00"), nb(2, "-5.00")])
        self.assertIn("rebuild", str(ctx.exception).lower())


# ─── Two-Person Tests ─────────────────────────────────────────────────────────

class TwoPersonTests(TestCase):
    def test_two_people_equal_produces_one_transaction(self):
        result = simplify_debts([nb(1, "100.00"), nb(2, "-100.00")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["amount"], D("100.00"))

    def test_payer_and_receiver_correct(self):
        result = simplify_debts([nb(1, "100.00"), nb(2, "-100.00")])
        self.assertEqual(result[0]["payer_id"], 2)    # debtor pays
        self.assertEqual(result[0]["receiver_id"], 1)  # creditor receives

    def test_partial_debt_produces_one_transaction(self):
        result = simplify_debts([nb(1, "80.00"), nb(2, "-80.00")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["amount"], D("80.00"))

    def test_decimal_precision_preserved(self):
        result = simplify_debts([nb(1, "33.33"), nb(2, "-33.33")])
        self.assertEqual(result[0]["amount"], D("33.33"))


# ─── One Creditor, Many Debtors ───────────────────────────────────────────────

class OneCreditManyDebtorsTests(TestCase):
    def test_one_creditor_two_debtors(self):
        # User 1 is owed 100; users 2 and 3 each owe 50
        result = simplify_debts([nb(1, "100.00"), nb(2, "-50.00"), nb(3, "-50.00")])
        self.assertEqual(len(result), 2)
        self.assertTrue(verify_settled(
            [nb(1, "100.00"), nb(2, "-50.00"), nb(3, "-50.00")], result
        ))

    def test_one_creditor_three_debtors_at_most_n_minus_1(self):
        balances = [nb(1, "90.00"), nb(2, "-30.00"), nb(3, "-30.00"), nb(4, "-30.00")]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 3)  # N=4, N-1=3
        self.assertTrue(verify_settled(balances, result))

    def test_one_creditor_unequal_debtors(self):
        balances = [nb(1, "90.00"), nb(2, "-60.00"), nb(3, "-30.00")]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 2)
        self.assertTrue(verify_settled(balances, result))
        # Largest debtor (60) should be addressed first
        self.assertEqual(result[0]["payer_id"], 2)


# ─── One Debtor, Many Creditors ───────────────────────────────────────────────

class OneDebtorManyCreditorsTests(TestCase):
    def test_one_debtor_two_creditors(self):
        balances = [nb(1, "60.00"), nb(2, "40.00"), nb(3, "-100.00")]
        result = simplify_debts(balances)
        self.assertEqual(len(result), 2)
        self.assertTrue(verify_settled(balances, result))

    def test_one_debtor_three_creditors(self):
        balances = [nb(1, "50.00"), nb(2, "30.00"), nb(3, "20.00"), nb(4, "-100.00")]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 3)
        self.assertTrue(verify_settled(balances, result))
        # All payers are user 4 (the only debtor)
        for t in result:
            self.assertEqual(t["payer_id"], 4)


# ─── Exact Cancellations ─────────────────────────────────────────────────────

class ExactCancellationTests(TestCase):
    def test_a_owes_b_b_owes_c_c_owes_a(self):
        """Circular debt — net positions should be zero for all."""
        # Each person in the circle owes and is owed the same amount → all zero
        # This simulates a cycle that has already been resolved at the Balance level
        result = simplify_debts([nb(1, "0.00"), nb(2, "0.00"), nb(3, "0.00")])
        self.assertEqual(result, [])

    def test_two_pairs_cancel_exactly(self):
        """A owes B 50, C owes D 50 — two independent transactions."""
        balances = [nb(1, "50.00"), nb(2, "-50.00"), nb(3, "50.00"), nb(4, "-50.00")]
        result = simplify_debts(balances)
        self.assertEqual(len(result), 2)
        self.assertTrue(verify_settled(balances, result))

    def test_mixed_creditor_debtor(self):
        """Some users are both partial creditors in one pair and debtors in another."""
        # A net: +30, B net: -10, C net: -20
        balances = [nb(1, "30.00"), nb(2, "-10.00"), nb(3, "-20.00")]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 2)
        self.assertTrue(verify_settled(balances, result))


# ─── Complex Multi-User Tests ─────────────────────────────────────────────────

class ComplexMultiUserTests(TestCase):
    def test_five_users_at_most_four_transactions(self):
        """N=5 → at most N-1=4 transactions."""
        balances = [
            nb(1, "120.00"),
            nb(2, "30.00"),
            nb(3, "-50.00"),
            nb(4, "-70.00"),
            nb(5, "-30.00"),
        ]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 4)
        self.assertTrue(verify_settled(balances, result))

    def test_six_users_at_most_five_transactions(self):
        balances = [
            nb(1, "100.00"),
            nb(2, "50.00"),
            nb(3, "25.00"),
            nb(4, "-75.00"),
            nb(5, "-60.00"),
            nb(6, "-40.00"),
        ]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 5)
        self.assertTrue(verify_settled(balances, result))

    def test_greedy_picks_largest_first(self):
        """Largest creditor and largest debtor paired first."""
        # Creditors: 1→70, 2→30  |  Debtors: 3→60, 4→40
        balances = [nb(1, "70.00"), nb(2, "30.00"), nb(3, "-60.00"), nb(4, "-40.00")]
        result = simplify_debts(balances)
        # First transaction: largest creditor (1) ← largest debtor (3)
        self.assertEqual(result[0]["payer_id"], 3)
        self.assertEqual(result[0]["receiver_id"], 1)

    def test_output_amount_ordering(self):
        """Output transactions sorted by amount descending."""
        balances = [nb(1, "100.00"), nb(2, "50.00"), nb(3, "-80.00"), nb(4, "-70.00")]
        result = simplify_debts(balances)
        amounts = [t["amount"] for t in result]
        self.assertEqual(amounts, sorted(amounts, reverse=True))


# ─── N-1 Bound Tests ──────────────────────────────────────────────────────────

class NMinus1BoundTests(TestCase):
    def test_n_minus_1_bound_2_users(self):
        result = simplify_debts([nb(1, "50.00"), nb(2, "-50.00")])
        self.assertLessEqual(len(result), 1)

    def test_n_minus_1_bound_3_users(self):
        result = simplify_debts([nb(1, "60.00"), nb(2, "-20.00"), nb(3, "-40.00")])
        self.assertLessEqual(len(result), 2)

    def test_n_minus_1_bound_4_users(self):
        result = simplify_debts([nb(1, "90.00"), nb(2, "-30.00"), nb(3, "-30.00"), nb(4, "-30.00")])
        self.assertLessEqual(len(result), 3)

    def test_n_minus_1_bound_balanced_pair(self):
        """If two users owe each other equal amounts, they cancel → fewer transactions."""
        # A owes 50, B is owed 50, C owes 50, D is owed 50, A↔B cancel, C↔D cancel
        balances = [nb(1, "50.00"), nb(2, "-50.00"), nb(3, "50.00"), nb(4, "-50.00")]
        result = simplify_debts(balances)
        self.assertLessEqual(len(result), 3)  # N=4, N-1=3


# ─── Decimal Precision Tests ──────────────────────────────────────────────────

class DecimalPrecisionTests(TestCase):
    def test_cent_level_precision(self):
        result = simplify_debts([nb(1, "0.01"), nb(2, "-0.01")])
        self.assertEqual(result[0]["amount"], D("0.01"))

    def test_large_amounts(self):
        result = simplify_debts([nb(1, "999999.99"), nb(2, "-999999.99")])
        self.assertEqual(result[0]["amount"], D("999999.99"))

    def test_asymmetric_decimal_splits(self):
        # 10/3 scenario: 3.34, 3.33, 3.33
        balances = [nb(1, "6.67"), nb(2, "-3.34"), nb(3, "-3.33")]
        result = simplify_debts(balances)
        self.assertTrue(verify_settled(balances, result))

    def test_no_floating_point_rounding_error(self):
        """Ensure we do not accumulate float error across many small transactions."""
        n = 10
        credit = D("100.00")
        each_debt = D("10.00")
        balances = [nb(1, str(credit))] + [nb(i + 2, str(-each_debt)) for i in range(n)]
        result = simplify_debts(balances)
        total_paid = sum(t["amount"] for t in result)
        self.assertEqual(total_paid, credit)


# ─── Determinism Tests ────────────────────────────────────────────────────────

class DeterminismTests(TestCase):
    def test_same_input_same_output(self):
        balances = [nb(1, "90.00"), nb(2, "-50.00"), nb(3, "-40.00")]
        result_a = simplify_debts(balances)
        result_b = simplify_debts(balances)
        self.assertEqual(result_a, result_b)

    def test_reversed_input_order_same_output(self):
        balances = [nb(1, "90.00"), nb(2, "-50.00"), nb(3, "-40.00")]
        reversed_balances = list(reversed(balances))
        result_a = simplify_debts(balances)
        result_b = simplify_debts(reversed_balances)
        # Amounts must be the same (order may differ if amounts differ but must match)
        self.assertEqual(
            sorted([(t["payer_id"], t["receiver_id"], t["amount"]) for t in result_a]),
            sorted([(t["payer_id"], t["receiver_id"], t["amount"]) for t in result_b]),
        )


# ─── DB Integration: compute_net_balances_for_group ───────────────────────────

class ComputeNetBalancesTests(TestCase):
    def setUp(self):
        self.a = mk_user("nb_a@x.com")
        self.b = mk_user("nb_b@x.com")
        self.c = mk_user("nb_c@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)
        add_member(self.group, self.c)

    def _place_balance(self, u1, u2, net_amount_str):
        uid1, uid2 = min(u1.id, u2.id), max(u1.id, u2.id)
        # net_amount > 0 → user2 owes user1
        # We want: u1 is owed the amount → set net_amount positive if u1=uid1
        if u1.id < u2.id:
            net = D(net_amount_str)
        else:
            net = -D(net_amount_str)
        Balance.objects.create(group=self.group, user1_id=uid1, user2_id=uid2, net_amount=net)

    def test_empty_group_returns_empty(self):
        result = compute_net_balances_for_group(self.group)
        self.assertEqual(result, [])

    def test_single_balance_row(self):
        # a is owed 60 by b
        self._place_balance(self.a, self.b, "60.00")
        result = compute_net_balances_for_group(self.group)
        amounts = {e["user_id"]: e["amount"] for e in result}
        self.assertEqual(amounts[self.a.id], D("60.00"))
        self.assertEqual(amounts[self.b.id], D("-60.00"))

    def test_multiple_balance_rows_aggregate(self):
        """User A is owed by B (60) and C (40) → A's net = +100."""
        self._place_balance(self.a, self.b, "60.00")
        self._place_balance(self.a, self.c, "40.00")
        result = compute_net_balances_for_group(self.group)
        amounts = {e["user_id"]: e["amount"] for e in result}
        self.assertEqual(amounts[self.a.id], D("100.00"))
        self.assertEqual(amounts[self.b.id], D("-60.00"))
        self.assertEqual(amounts[self.c.id], D("-40.00"))

    def test_zero_net_users_excluded(self):
        """User with zero net position is excluded from output."""
        # a owed by b 50; b owed by c 50 → b's net = 0
        self._place_balance(self.a, self.b, "50.00")
        self._place_balance(self.b, self.c, "50.00")
        result = compute_net_balances_for_group(self.group)
        user_ids = [e["user_id"] for e in result]
        self.assertNotIn(self.b.id, user_ids)

    def test_net_sum_is_zero(self):
        """Sum of all net balances must always be zero."""
        self._place_balance(self.a, self.b, "70.00")
        self._place_balance(self.a, self.c, "30.00")
        result = compute_net_balances_for_group(self.group)
        self.assertEqual(sum(e["amount"] for e in result), D("0.00"))


# ─── DB Integration: get_simplified_debts_for_group ──────────────────────────

class GetSimplifiedDebtsForGroupTests(TestCase):
    def setUp(self):
        self.a = mk_user("gs_a@x.com")
        self.b = mk_user("gs_b@x.com")
        self.c = mk_user("gs_c@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)
        add_member(self.group, self.c)

    def _expense(self, payer, splits_data):
        exp = Expense.objects.create(
            group=self.group, paid_by=payer, created_by=payer,
            description="X", amount=sum(D(a) for _, a in splits_data),
            category=Expense.CATEGORY_FOOD, expense_date=date.today(),
            split_type=Expense.SPLIT_EQUAL,
        )
        splits = [ExpenseSplit.objects.create(expense=exp, user=u, amount=D(a)) for u, a in splits_data]
        apply_expense_to_balances(exp, splits)
        return exp, splits

    def test_no_balances_returns_empty(self):
        result = get_simplified_debts_for_group(self.group)
        self.assertEqual(result, [])

    def test_two_person_settled_by_one_transaction(self):
        # A pays $100, B owes $100
        self._expense(self.a, [(self.a, "0.00"), (self.b, "100.00")])
        result = get_simplified_debts_for_group(self.group)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["payer_id"], self.b.id)
        self.assertEqual(result[0]["receiver_id"], self.a.id)
        self.assertEqual(result[0]["amount"], D("100.00"))

    def test_three_person_two_expenses(self):
        # A pays $90 split 3 ways → B, C each owe A $30
        self._expense(self.a, [(self.a, "30.00"), (self.b, "30.00"), (self.c, "30.00")])
        result = get_simplified_debts_for_group(self.group)
        self.assertLessEqual(len(result), 2)
        total = sum(t["amount"] for t in result)
        self.assertEqual(total, D("60.00"))

    def test_fully_settled_group_returns_empty(self):
        self._expense(self.a, [(self.a, "0.00"), (self.b, "50.00")])
        # Simulate settlement by directly zeroing balance
        Balance.objects.filter(group=self.group).delete()
        result = get_simplified_debts_for_group(self.group)
        self.assertEqual(result, [])

    def test_cross_group_isolation(self):
        other_user = mk_user("gs_other@x.com")
        group2 = mk_group(other_user)
        add_member(group2, self.b)

        self._expense(self.a, [(self.a, "0.00"), (self.b, "40.00")])
        exp2 = Expense.objects.create(
            group=group2, paid_by=other_user, created_by=other_user,
            description="Y", amount=D("200.00"),
            category=Expense.CATEGORY_FOOD, expense_date=date.today(),
            split_type=Expense.SPLIT_EQUAL,
        )
        sp2 = [ExpenseSplit.objects.create(expense=exp2, user=self.b, amount=D("200.00"))]
        apply_expense_to_balances(exp2, sp2)

        result = get_simplified_debts_for_group(self.group)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["amount"], D("40.00"))
