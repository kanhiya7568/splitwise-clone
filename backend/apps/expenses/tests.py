"""
Module 5A — Expense domain logic tests.
Tests validators and services. Views are not tested here (Module 5B).

Run: python manage.py test apps.expenses
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.expenses.models import Expense, ExpenseSplit
from apps.expenses.validators import (
    ExpenseValidationError,
    calculate_equal_splits,
    validate_no_duplicate_participants,
    validate_participants_are_group_members,
    validate_payer_is_participant,
    validate_percentage_splits,
    validate_shares_splits,
    validate_unequal_splits,
)
from apps.expenses import services
from apps.expenses.services import ExpenseServiceError
from apps.groups.models import Group, GroupMembership
from apps.users.models import User


# ─── helpers ──────────────────────────────────────────────────────────────────

def mk_user(email="u@x.com", **kw):
    return User.objects.create_user(email=email, password="Pass1word", first_name="T", last_name="U", **kw)

def mk_group(creator):
    g = Group.objects.create(name="G", created_by=creator)
    GroupMembership.objects.create(group=g, user=creator, role=GroupMembership.ROLE_ADMIN)
    return g

def add_member(group, user):
    return GroupMembership.objects.create(group=group, user=user, role=GroupMembership.ROLE_MEMBER)

def mk_expense(group, creator, payer=None, amount="90.00", split_type=Expense.SPLIT_EQUAL, participants=None):
    payer = payer or creator
    participants = participants or [creator]
    expense, splits = services.create_expense(
        group=group, created_by=creator, paid_by_id=payer.id,
        description="Dinner", amount=Decimal(amount),
        category=Expense.CATEGORY_FOOD, expense_date=date.today(),
        split_type=split_type, splits_input=[],
        participant_ids=[u.id for u in participants],
    )
    return expense, splits

D = Decimal


# ─── Equal Split Validator Tests ──────────────────────────────────────────────

class EqualSplitTests(TestCase):
    def test_two_equal_parts(self):
        splits = calculate_equal_splits(D("100.00"), [1, 2], payer_id=1)
        amounts = {s["user_id"]: s["amount"] for s in splits}
        self.assertEqual(amounts[1] + amounts[2], D("100.00"))
        self.assertEqual(amounts[1], amounts[2])

    def test_remainder_goes_to_payer(self):
        # 10.00 / 3 = 3.33 + 3.33 + 3.34 (payer gets 3.34)
        splits = calculate_equal_splits(D("10.00"), [1, 2, 3], payer_id=1)
        amounts = {s["user_id"]: s["amount"] for s in splits}
        self.assertEqual(amounts[1], D("3.34"))
        self.assertEqual(amounts[2], D("3.33"))
        self.assertEqual(amounts[3], D("3.33"))
        self.assertEqual(sum(amounts.values()), D("10.00"))

    def test_single_participant_gets_full_amount(self):
        splits = calculate_equal_splits(D("50.00"), [5], payer_id=5)
        self.assertEqual(splits[0]["amount"], D("50.00"))

    def test_sum_always_equals_total(self):
        for cents in range(1, 100):
            total = D(f"0.{cents:02d}")
            splits = calculate_equal_splits(total, [1, 2, 3], payer_id=1)
            self.assertEqual(sum(s["amount"] for s in splits), total)

    def test_none_field_set(self):
        splits = calculate_equal_splits(D("30.00"), [1, 2, 3], payer_id=1)
        for s in splits:
            self.assertIsNone(s["percentage"])
            self.assertIsNone(s["shares"])

    def test_empty_participants_raises(self):
        with self.assertRaises(ExpenseValidationError):
            calculate_equal_splits(D("100.00"), [], payer_id=1)


# ─── Unequal Split Validator Tests ────────────────────────────────────────────

class UnequalSplitTests(TestCase):
    def test_valid_unequal_split(self):
        splits = validate_unequal_splits(
            D("100.00"), [{"user_id": 1, "amount": D("60.00")}, {"user_id": 2, "amount": D("40.00")}]
        )
        self.assertEqual(len(splits), 2)

    def test_sum_not_equal_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_unequal_splits(
                D("100.00"), [{"user_id": 1, "amount": D("60.00")}, {"user_id": 2, "amount": D("30.00")}]
            )

    def test_sum_exceeds_total_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_unequal_splits(
                D("100.00"), [{"user_id": 1, "amount": D("60.00")}, {"user_id": 2, "amount": D("50.00")}]
            )

    def test_negative_amount_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_unequal_splits(
                D("100.00"), [{"user_id": 1, "amount": D("-10.00")}, {"user_id": 2, "amount": D("110.00")}]
            )

    def test_zero_amount_allowed(self):
        splits = validate_unequal_splits(
            D("100.00"), [{"user_id": 1, "amount": D("0.00")}, {"user_id": 2, "amount": D("100.00")}]
        )
        self.assertEqual(splits[0]["amount"], D("0.00"))

    def test_empty_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_unequal_splits(D("100.00"), [])


# ─── Percentage Split Validator Tests ─────────────────────────────────────────

class PercentageSplitTests(TestCase):
    def _run(self, total, items):
        return validate_percentage_splits(D(total), items)

    def test_50_50_split(self):
        splits = self._run("100.00", [{"user_id": 1, "percentage": D("50.00")}, {"user_id": 2, "percentage": D("50.00")}])
        self.assertEqual(sum(s["amount"] for s in splits), D("100.00"))

    def test_last_participant_gets_remainder(self):
        # 33.33 + 33.33 + 33.34 = 100.00
        splits = self._run("100.00", [
            {"user_id": 1, "percentage": D("33.33")},
            {"user_id": 2, "percentage": D("33.33")},
            {"user_id": 3, "percentage": D("33.34")},
        ])
        self.assertEqual(sum(s["amount"] for s in splits), D("100.00"))

    def test_tolerance_99_99_accepted(self):
        splits = self._run("100.00", [
            {"user_id": 1, "percentage": D("33.33")},
            {"user_id": 2, "percentage": D("33.33")},
            {"user_id": 3, "percentage": D("33.33")},
        ])
        self.assertEqual(sum(s["amount"] for s in splits), D("100.00"))

    def test_101_percent_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [{"user_id": 1, "percentage": D("51.00")}, {"user_id": 2, "percentage": D("50.00")}])

    def test_98_percent_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [{"user_id": 1, "percentage": D("48.00")}, {"user_id": 2, "percentage": D("50.00")}])

    def test_negative_percentage_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [{"user_id": 1, "percentage": D("-10.00")}, {"user_id": 2, "percentage": D("110.00")}])

    def test_100_percent_one_person(self):
        splits = self._run("75.00", [{"user_id": 1, "percentage": D("100.00")}])
        self.assertEqual(splits[0]["amount"], D("75.00"))

    def test_percentage_field_set(self):
        splits = self._run("100.00", [{"user_id": 1, "percentage": D("100.00")}])
        self.assertEqual(splits[0]["percentage"], D("100.00"))
        self.assertIsNone(splits[0]["shares"])


# ─── Shares Split Validator Tests ─────────────────────────────────────────────

class SharesSplitTests(TestCase):
    def _run(self, total, items):
        return validate_shares_splits(D(total), items)

    def test_equal_shares(self):
        splits = self._run("90.00", [{"user_id": 1, "shares": D("1")}, {"user_id": 2, "shares": D("1")}, {"user_id": 3, "shares": D("1")}])
        self.assertEqual(sum(s["amount"] for s in splits), D("90.00"))
        self.assertEqual(splits[0]["amount"], D("30.00"))

    def test_weighted_shares(self):
        splits = self._run("100.00", [{"user_id": 1, "shares": D("1")}, {"user_id": 2, "shares": D("3")}])
        self.assertEqual(sum(s["amount"] for s in splits), D("100.00"))
        self.assertEqual(splits[0]["amount"], D("25.00"))
        self.assertEqual(splits[1]["amount"], D("75.00"))

    def test_zero_shares_all_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [{"user_id": 1, "shares": D("0")}, {"user_id": 2, "shares": D("0")}])

    def test_zero_share_participant_gets_zero(self):
        splits = self._run("100.00", [{"user_id": 1, "shares": D("0")}, {"user_id": 2, "shares": D("1")}])
        amounts = {s["user_id"]: s["amount"] for s in splits}
        self.assertEqual(amounts[1], D("0.00"))
        self.assertEqual(amounts[2], D("100.00"))

    def test_negative_shares_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [{"user_id": 1, "shares": D("-1")}, {"user_id": 2, "shares": D("2")}])

    def test_empty_raises(self):
        with self.assertRaises(ExpenseValidationError):
            self._run("100.00", [])


# ─── Participant Validator Tests ──────────────────────────────────────────────

class ParticipantValidatorTests(TestCase):
    def setUp(self):
        self.admin = mk_user("adm@x.com")
        self.member = mk_user("mem@x.com")
        self.outsider = mk_user("out@x.com")
        self.group = mk_group(self.admin)
        add_member(self.group, self.member)

    def test_valid_members_pass(self):
        validate_participants_are_group_members(self.group, [self.admin.id, self.member.id])

    def test_outsider_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_participants_are_group_members(self.group, [self.admin.id, self.outsider.id])

    def test_empty_list_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_participants_are_group_members(self.group, [])

    def test_payer_in_participants_passes(self):
        validate_payer_is_participant(self.admin.id, [self.admin.id, self.member.id])

    def test_payer_not_in_participants_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_payer_is_participant(self.admin.id, [self.member.id])

    def test_duplicate_participants_raises(self):
        with self.assertRaises(ExpenseValidationError):
            validate_no_duplicate_participants([1, 2, 1])

    def test_unique_participants_passes(self):
        validate_no_duplicate_participants([1, 2, 3])


# ─── Create Expense Service Tests ─────────────────────────────────────────────

class CreateExpenseServiceTests(TestCase):
    def setUp(self):
        self.admin = mk_user("ca@x.com")
        self.member = mk_user("cm@x.com")
        self.group = mk_group(self.admin)
        add_member(self.group, self.member)

    def test_create_equal_expense(self):
        expense, splits = mk_expense(self.group, self.admin, participants=[self.admin, self.member])
        self.assertIsNotNone(expense.pk)
        self.assertEqual(len(splits), 2)

    def test_splits_sum_to_amount(self):
        expense, splits = mk_expense(self.group, self.admin, amount="100.00", participants=[self.admin, self.member])
        self.assertEqual(sum(s.amount for s in splits), D("100.00"))

    def test_creator_can_set_different_payer(self):
        expense, _ = mk_expense(self.group, self.admin, payer=self.member, participants=[self.admin, self.member])
        self.assertEqual(expense.paid_by_id, self.member.id)

    def test_outsider_cannot_create_expense(self):
        outsider = mk_user("out@x.com")
        with self.assertRaises(PermissionDenied):
            mk_expense(self.group, outsider, participants=[self.admin])

    def test_payer_not_in_group_raises(self):
        outsider = mk_user("out2@x.com")
        with self.assertRaises(ExpenseServiceError):
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=outsider.id,
                description="X", amount=D("50.00"), category=Expense.CATEGORY_FOOD,
                expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                splits_input=[], participant_ids=[self.admin.id],
            )

    def test_payer_not_in_participants_raises(self):
        with self.assertRaises(ExpenseServiceError):
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
                description="X", amount=D("50.00"), category=Expense.CATEGORY_FOOD,
                expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                splits_input=[], participant_ids=[self.member.id],  # payer not in list
            )

    def test_non_member_participant_raises(self):
        outsider = mk_user("out3@x.com")
        with self.assertRaises(ExpenseServiceError):
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
                description="X", amount=D("50.00"), category=Expense.CATEGORY_FOOD,
                expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                splits_input=[], participant_ids=[self.admin.id, outsider.id],
            )

    def test_create_unequal_expense(self):
        expense, splits = services.create_expense(
            group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
            description="Dinner", amount=D("70.00"), category=Expense.CATEGORY_FOOD,
            expense_date=date.today(), split_type=Expense.SPLIT_UNEQUAL,
            splits_input=[
                {"user_id": self.admin.id, "amount": D("40.00")},
                {"user_id": self.member.id, "amount": D("30.00")},
            ],
            participant_ids=[self.admin.id, self.member.id],
        )
        self.assertEqual(expense.split_type, Expense.SPLIT_UNEQUAL)
        self.assertEqual(sum(s.amount for s in splits), D("70.00"))

    def test_create_percentage_expense(self):
        expense, splits = services.create_expense(
            group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
            description="Hotel", amount=D("100.00"), category=Expense.CATEGORY_ACCOMMODATION,
            expense_date=date.today(), split_type=Expense.SPLIT_PERCENTAGE,
            splits_input=[
                {"user_id": self.admin.id, "percentage": D("60.00")},
                {"user_id": self.member.id, "percentage": D("40.00")},
            ],
            participant_ids=[self.admin.id, self.member.id],
        )
        self.assertEqual(sum(s.amount for s in splits), D("100.00"))

    def test_create_shares_expense(self):
        expense, splits = services.create_expense(
            group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
            description="Fuel", amount=D("90.00"), category=Expense.CATEGORY_TRANSPORT,
            expense_date=date.today(), split_type=Expense.SPLIT_SHARES,
            splits_input=[
                {"user_id": self.admin.id, "shares": D("2")},
                {"user_id": self.member.id, "shares": D("1")},
            ],
            participant_ids=[self.admin.id, self.member.id],
        )
        amounts = {s.user_id: s.amount for s in splits}
        self.assertEqual(amounts[self.admin.id], D("60.00"))
        self.assertEqual(amounts[self.member.id], D("30.00"))

    def test_expense_is_not_deleted_on_create(self):
        expense, _ = mk_expense(self.group, self.admin, participants=[self.admin])
        self.assertFalse(expense.is_deleted)

    def test_unequal_sum_mismatch_raises(self):
        with self.assertRaises(ExpenseServiceError):
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
                description="X", amount=D("100.00"), category=Expense.CATEGORY_FOOD,
                expense_date=date.today(), split_type=Expense.SPLIT_UNEQUAL,
                splits_input=[
                    {"user_id": self.admin.id, "amount": D("40.00")},
                    {"user_id": self.member.id, "amount": D("40.00")},
                ],
                participant_ids=[self.admin.id, self.member.id],
            )

    def test_duplicate_participant_raises(self):
        with self.assertRaises(ExpenseServiceError):
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
                description="X", amount=D("100.00"), category=Expense.CATEGORY_FOOD,
                expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                splits_input=[], participant_ids=[self.admin.id, self.admin.id],
            )


# ─── Update Expense Service Tests ─────────────────────────────────────────────

class UpdateExpenseServiceTests(TestCase):
    def setUp(self):
        self.admin = mk_user("ua@x.com")
        self.member = mk_user("um@x.com")
        self.group = mk_group(self.admin)
        add_member(self.group, self.member)
        self.expense, _ = mk_expense(
            self.group, self.admin, participants=[self.admin, self.member]
        )

    def test_creator_can_update_description(self):
        expense, _ = services.update_expense(self.expense, self.admin, description="New Desc")
        self.assertEqual(expense.description, "New Desc")

    def test_admin_can_update_others_expense(self):
        member_expense, _ = mk_expense(self.group, self.member, participants=[self.admin, self.member])
        expense, _ = services.update_expense(member_expense, self.admin, description="Fixed")
        self.assertEqual(expense.description, "Fixed")

    def test_non_creator_non_admin_cannot_update(self):
        other = mk_user("other@x.com")
        add_member(self.group, other)
        with self.assertRaises(PermissionDenied):
            services.update_expense(self.expense, other, description="Hack")

    def test_update_recreates_splits(self):
        third = mk_user("third@x.com")
        add_member(self.group, third)
        expense, splits = services.update_expense(
            self.expense, self.admin,
            amount=D("90.00"),
            split_type=Expense.SPLIT_EQUAL,
            participant_ids=[self.admin.id, self.member.id, third.id],
            splits_input=[],
        )
        self.assertEqual(len(splits), 3)
        self.assertEqual(sum(s.amount for s in splits), D("90.00"))

    def test_old_splits_deleted_on_update(self):
        old_count = ExpenseSplit.objects.filter(expense=self.expense).count()
        services.update_expense(
            self.expense, self.admin,
            amount=D("60.00"),
            participant_ids=[self.admin.id],
            splits_input=[],
        )
        new_count = ExpenseSplit.objects.filter(expense=self.expense).count()
        self.assertNotEqual(old_count, new_count)
        self.assertEqual(new_count, 1)

    def test_update_preserves_unchanged_fields(self):
        original_amount = self.expense.amount
        expense, _ = services.update_expense(self.expense, self.admin, description="Changed Only")
        self.assertEqual(expense.amount, original_amount)


# ─── Delete Expense Service Tests ─────────────────────────────────────────────

class DeleteExpenseServiceTests(TestCase):
    def setUp(self):
        self.admin = mk_user("da@x.com")
        self.member = mk_user("dm@x.com")
        self.group = mk_group(self.admin)
        add_member(self.group, self.member)
        self.expense, _ = mk_expense(self.group, self.admin, participants=[self.admin])

    def test_creator_can_delete(self):
        result = services.delete_expense(self.expense, self.admin)
        result.refresh_from_db()
        self.assertTrue(result.is_deleted)

    def test_admin_can_delete_others_expense(self):
        member_expense, _ = mk_expense(self.group, self.member, participants=[self.member])
        services.delete_expense(member_expense, self.admin)
        member_expense.refresh_from_db()
        self.assertTrue(member_expense.is_deleted)

    def test_non_creator_non_admin_cannot_delete(self):
        other = mk_user("other2@x.com")
        add_member(self.group, other)
        with self.assertRaises(PermissionDenied):
            services.delete_expense(self.expense, other)

    def test_already_deleted_raises(self):
        services.delete_expense(self.expense, self.admin)
        with self.assertRaises(ExpenseServiceError):
            services.delete_expense(self.expense, self.admin)

    def test_splits_preserved_after_delete(self):
        split_count = ExpenseSplit.objects.filter(expense=self.expense).count()
        services.delete_expense(self.expense, self.admin)
        self.assertEqual(ExpenseSplit.objects.filter(expense=self.expense).count(), split_count)


# ─── Expense History Service Tests ────────────────────────────────────────────

class ExpenseHistoryServiceTests(TestCase):
    def setUp(self):
        self.admin = mk_user("ha@x.com")
        self.member = mk_user("hm@x.com")
        self.group = mk_group(self.admin)
        add_member(self.group, self.member)

        for desc, cat, amt in [
            ("Dinner", Expense.CATEGORY_FOOD, "60.00"),
            ("Taxi", Expense.CATEGORY_TRANSPORT, "30.00"),
            ("Hotel", Expense.CATEGORY_ACCOMMODATION, "200.00"),
        ]:
            services.create_expense(
                group=self.group, created_by=self.admin, paid_by_id=self.admin.id,
                description=desc, amount=D(amt), category=cat,
                expense_date=date.today(), split_type=Expense.SPLIT_EQUAL,
                splits_input=[], participant_ids=[self.admin.id],
            )

    def test_member_sees_all_expenses(self):
        qs = services.get_expense_history(self.group, self.member)
        self.assertEqual(qs.count(), 3)

    def test_outsider_cannot_see_history(self):
        outsider = mk_user("hout@x.com")
        with self.assertRaises(PermissionDenied):
            services.get_expense_history(self.group, outsider)

    def test_deleted_expenses_excluded(self):
        expense, _ = mk_expense(self.group, self.admin, participants=[self.admin])
        services.delete_expense(expense, self.admin)
        qs = services.get_expense_history(self.group, self.admin)
        self.assertNotIn(expense.id, qs.values_list("id", flat=True))

    def test_filter_by_category(self):
        qs = services.get_expense_history(self.group, self.admin, category=Expense.CATEGORY_FOOD)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().description, "Dinner")

    def test_filter_by_paid_by(self):
        qs = services.get_expense_history(self.group, self.admin, paid_by_id=self.admin.id)
        self.assertEqual(qs.count(), 3)

    def test_filter_by_paid_by_other_returns_empty(self):
        qs = services.get_expense_history(self.group, self.admin, paid_by_id=self.member.id)
        self.assertEqual(qs.count(), 0)

    def test_filter_by_date_range(self):
        qs = services.get_expense_history(
            self.group, self.admin,
            from_date=date.today(),
            to_date=date.today(),
        )
        self.assertEqual(qs.count(), 3)
