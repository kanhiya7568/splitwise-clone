"""
Expense API tests — Module 5B.

Tests the HTTP endpoints. Service-layer logic is tested in tests.py (Module 5A).

Run: python manage.py test apps.expenses.tests_api
"""

from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.balances.models import Balance
from apps.expenses.models import Expense, ExpenseSplit
from apps.groups.models import Group, GroupMembership
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


def list_url(gid):
    return reverse("expense_list_create", kwargs={"gid": gid})


def detail_url(gid, eid):
    return reverse("expense_detail", kwargs={"gid": gid, "eid": eid})


def edit_url(gid, eid):
    return reverse("expense_update", kwargs={"gid": gid, "eid": eid})


def delete_url(gid, eid):
    return reverse("expense_delete", kwargs={"gid": gid, "eid": eid})


def net_balance(group, u1, u2):
    uid1, uid2 = min(u1.id, u2.id), max(u1.id, u2.id)
    b = Balance.objects.filter(group=group, user1_id=uid1, user2_id=uid2).first()
    return b.net_amount if b else D("0.00")


# ─── Equal Split API Tests ────────────────────────────────────────────────────

class CreateEqualSplitTests(APITestCase):
    def setUp(self):
        self.a = mk_user("eq_a@x.com")
        self.b = mk_user("eq_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def payload(self, **kwargs):
        base = {
            "description": "Dinner",
            "amount": "90.00",
            "split_type": "equal",
            "expense_date": str(date.today()),
            "splits": [{"user_id": self.a.id}, {"user_id": self.b.id}],
        }
        base.update(kwargs)
        return base

    def test_equal_split_201(self):
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_response_has_splits(self):
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        self.assertIn("splits", r.json())
        self.assertEqual(len(r.json()["splits"]), 2)

    def test_splits_sum_to_amount(self):
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        splits = r.json()["splits"]
        total = sum(D(s["amount"]) for s in splits)
        self.assertEqual(total, D("90.00"))

    def test_balance_updated_after_create(self):
        self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)

    def test_unauthenticated_401(self):
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_outsider_403(self):
        outsider = mk_user("eq_out@x.com")
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_blank_description_400(self):
        r = self.client.post(list_url(self.group.pk), self.payload(description="  "), format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_amount_400(self):
        r = self.client.post(list_url(self.group.pk), self.payload(amount="0.00"), format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_subset_participation_equal(self):
        """Only A and B participate (not a third member)."""
        c = mk_user("eq_c@x.com")
        add_member(self.group, c)
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        splits = r.json()["splits"]
        uids = [s["user"]["id"] for s in splits]
        self.assertNotIn(c.id, uids)

    def test_paid_by_defaults_to_creator(self):
        r = self.client.post(list_url(self.group.pk), self.payload(), format="json", **auth(self.a))
        self.assertEqual(r.json()["paid_by"]["id"], self.a.id)


# ─── Unequal Split API Tests ──────────────────────────────────────────────────

class CreateUnequalSplitTests(APITestCase):
    def setUp(self):
        self.a = mk_user("un_a@x.com")
        self.b = mk_user("un_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_unequal_split_201(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Dinner",
            "amount": "70.00",
            "split_type": "unequal",
            "splits": [{"user_id": self.a.id, "amount": "40.00"}, {"user_id": self.b.id, "amount": "30.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_unequal_sum_mismatch_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Dinner",
            "amount": "70.00",
            "split_type": "unequal",
            "splits": [{"user_id": self.a.id, "amount": "40.00"}, {"user_id": self.b.id, "amount": "20.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_split_amount_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "D",
            "amount": "70.00",
            "split_type": "unequal",
            "splits": [{"user_id": self.a.id, "amount": "-10.00"}, {"user_id": self.b.id, "amount": "80.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unequal_balance_correct(self):
        self.client.post(list_url(self.group.pk), {
            "description": "Dinner",
            "amount": "70.00",
            "split_type": "unequal",
            "splits": [{"user_id": self.a.id, "amount": "0.00"}, {"user_id": self.b.id, "amount": "70.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(abs(net_balance(self.group, self.a, self.b)), D("70.00"))


# ─── Percentage Split API Tests ───────────────────────────────────────────────

class CreatePercentageSplitTests(APITestCase):
    def setUp(self):
        self.a = mk_user("pct_a@x.com")
        self.b = mk_user("pct_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_percentage_split_201(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Hotel",
            "amount": "100.00",
            "split_type": "percentage",
            "splits": [{"user_id": self.a.id, "percentage": "60.00"}, {"user_id": self.b.id, "percentage": "40.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_percentage_not_100_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Hotel",
            "amount": "100.00",
            "split_type": "percentage",
            "splits": [{"user_id": self.a.id, "percentage": "50.00"}, {"user_id": self.b.id, "percentage": "30.00"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_percentage_amounts_sum_to_total(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Hotel",
            "amount": "100.00",
            "split_type": "percentage",
            "splits": [{"user_id": self.a.id, "percentage": "60.00"}, {"user_id": self.b.id, "percentage": "40.00"}],
        }, format="json", **auth(self.a))
        splits = r.json()["splits"]
        self.assertEqual(sum(D(s["amount"]) for s in splits), D("100.00"))


# ─── Shares Split API Tests ───────────────────────────────────────────────────

class CreateSharesSplitTests(APITestCase):
    def setUp(self):
        self.a = mk_user("sh_a@x.com")
        self.b = mk_user("sh_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_shares_split_201(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Taxi",
            "amount": "90.00",
            "split_type": "shares",
            "splits": [{"user_id": self.a.id, "shares": "2"}, {"user_id": self.b.id, "shares": "1"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_shares_proportional_amounts(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Taxi",
            "amount": "90.00",
            "split_type": "shares",
            "splits": [{"user_id": self.a.id, "shares": "2"}, {"user_id": self.b.id, "shares": "1"}],
        }, format="json", **auth(self.a))
        splits = {s["user"]["id"]: D(s["amount"]) for s in r.json()["splits"]}
        self.assertEqual(splits[self.a.id], D("60.00"))
        self.assertEqual(splits[self.b.id], D("30.00"))

    def test_all_zero_shares_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "Taxi",
            "amount": "90.00",
            "split_type": "shares",
            "splits": [{"user_id": self.a.id, "shares": "0"}, {"user_id": self.b.id, "shares": "0"}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Participant Validation Tests ─────────────────────────────────────────────

class ParticipantValidationTests(APITestCase):
    def setUp(self):
        self.a = mk_user("pv_a@x.com")
        self.b = mk_user("pv_b@x.com")
        self.outsider = mk_user("pv_out@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def test_non_member_participant_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "D",
            "amount": "60.00",
            "split_type": "equal",
            "splits": [{"user_id": self.a.id}, {"user_id": self.outsider.id}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payer_not_in_splits_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "D",
            "amount": "60.00",
            "split_type": "equal",
            "paid_by": self.a.id,
            "splits": [{"user_id": self.b.id}],  # payer not included
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_participant_400(self):
        r = self.client.post(list_url(self.group.pk), {
            "description": "D",
            "amount": "60.00",
            "split_type": "equal",
            "splits": [{"user_id": self.a.id}, {"user_id": self.a.id}],
        }, format="json", **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ─── List and Retrieve Tests ──────────────────────────────────────────────────

class ListRetrieveTests(APITestCase):
    def setUp(self):
        self.a = mk_user("lr_a@x.com")
        self.b = mk_user("lr_b@x.com")
        self.outsider = mk_user("lr_out@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)
        # Create 3 expenses
        for i in range(3):
            self.client.post(list_url(self.group.pk), {
                "description": f"Exp{i}",
                "amount": "30.00",
                "split_type": "equal",
                "splits": [{"user_id": self.a.id}],
            }, format="json", **auth(self.a))

    def test_list_returns_all_expenses(self):
        r = self.client.get(list_url(self.group.pk), **auth(self.a))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 3)

    def test_member_can_list(self):
        r = self.client.get(list_url(self.group.pk), **auth(self.b))
        self.assertEqual(r.status_code, 200)

    def test_outsider_cannot_list_403(self):
        r = self.client.get(list_url(self.group.pk), **auth(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_expense_200(self):
        exp = Expense.objects.filter(group=self.group).first()
        r = self.client.get(detail_url(self.group.pk, exp.pk), **auth(self.a))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], exp.pk)

    def test_outsider_cannot_retrieve_403(self):
        exp = Expense.objects.filter(group=self.group).first()
        r = self.client.get(detail_url(self.group.pk, exp.pk), **auth(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_expense_returns_404(self):
        exp = Expense.objects.filter(group=self.group).first()
        exp.soft_delete()
        r = self.client.get(detail_url(self.group.pk, exp.pk), **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination_uses_count_and_results(self):
        r = self.client.get(list_url(self.group.pk), **auth(self.a))
        data = r.json()
        self.assertIn("count", data)
        self.assertIn("results", data)

    def test_newest_first_ordering(self):
        r = self.client.get(list_url(self.group.pk), **auth(self.a))
        results = r.json()["results"]
        ids = [item["id"] for item in results]
        self.assertEqual(ids, sorted(ids, reverse=True))


# ─── Filtering Tests ──────────────────────────────────────────────────────────

class FilteringTests(APITestCase):
    def setUp(self):
        self.a = mk_user("filt_a@x.com")
        self.group = mk_group(self.a)
        today = date.today()
        yesterday = today - timedelta(days=1)

        self.client.post(list_url(self.group.pk), {
            "description": "Food",
            "amount": "50.00",
            "split_type": "equal",
            "category": "food",
            "expense_date": str(today),
            "splits": [{"user_id": self.a.id}],
        }, format="json", **auth(self.a))

        self.client.post(list_url(self.group.pk), {
            "description": "Taxi",
            "amount": "30.00",
            "split_type": "equal",
            "category": "transport",
            "expense_date": str(yesterday),
            "splits": [{"user_id": self.a.id}],
        }, format="json", **auth(self.a))

    def test_filter_by_category(self):
        r = self.client.get(
            list_url(self.group.pk), {"category": "food"}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(r.json()["results"][0]["description"], "Food")

    def test_filter_by_split_type(self):
        r = self.client.get(
            list_url(self.group.pk), {"split_type": "equal"}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 2)

    def test_filter_by_date_from(self):
        r = self.client.get(
            list_url(self.group.pk),
            {"date_from": str(date.today())},
            **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 1)

    def test_filter_by_date_to(self):
        yesterday = str(date.today() - timedelta(days=1))
        r = self.client.get(
            list_url(self.group.pk), {"date_to": yesterday}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 1)

    def test_filter_by_created_by(self):
        r = self.client.get(
            list_url(self.group.pk), {"created_by": self.a.id}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 2)

    def test_invalid_category_ignored(self):
        r = self.client.get(
            list_url(self.group.pk), {"category": "notacategory"}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 2)

    def test_invalid_date_ignored(self):
        r = self.client.get(
            list_url(self.group.pk), {"date_from": "not-a-date"}, **auth(self.a)
        )
        self.assertEqual(r.json()["count"], 2)


# ─── Update and Delete Permission Tests ───────────────────────────────────────

class UpdateDeletePermissionTests(APITestCase):
    def setUp(self):
        self.creator = mk_user("ud_creator@x.com")
        self.member = mk_user("ud_member@x.com")
        self.outsider = mk_user("ud_out@x.com")
        self.group = mk_group(self.creator)
        add_member(self.group, self.member)

        r = self.client.post(list_url(self.group.pk), {
            "description": "Dinner",
            "amount": "60.00",
            "split_type": "equal",
            "splits": [{"user_id": self.creator.id}],
        }, format="json", **auth(self.creator))
        self.expense_id = r.json()["id"]

    def test_creator_can_update(self):
        r = self.client.patch(
            edit_url(self.group.pk, self.expense_id),
            {"description": "Updated"},
            format="json", **auth(self.creator)
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["description"], "Updated")

    def test_member_cannot_update_403(self):
        r = self.client.patch(
            edit_url(self.group.pk, self.expense_id),
            {"description": "Hack"},
            format="json", **auth(self.member)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_others_expense(self):
        # Creator is admin; let's make member the expense creator
        r = self.client.post(list_url(self.group.pk), {
            "description": "MemberExpense",
            "amount": "30.00",
            "split_type": "equal",
            "splits": [{"user_id": self.member.id}],
        }, format="json", **auth(self.member))
        eid = r.json()["id"]
        r2 = self.client.patch(
            edit_url(self.group.pk, eid),
            {"description": "AdminEdited"},
            format="json", **auth(self.creator)  # creator is admin
        )
        self.assertEqual(r2.status_code, 200)

    def test_creator_can_delete(self):
        r = self.client.delete(
            delete_url(self.group.pk, self.expense_id), **auth(self.creator)
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Expense.objects.get(pk=self.expense_id).is_deleted == False)

    def test_member_cannot_delete_403(self):
        r = self.client.delete(
            delete_url(self.group.pk, self.expense_id), **auth(self.member)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_delete_403(self):
        r = self.client.delete(
            delete_url(self.group.pk, self.expense_id), **auth(self.outsider)
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_expense_not_in_list(self):
        self.client.delete(
            delete_url(self.group.pk, self.expense_id), **auth(self.creator)
        )
        r = self.client.get(list_url(self.group.pk), **auth(self.creator))
        ids = [e["id"] for e in r.json()["results"]]
        self.assertNotIn(self.expense_id, ids)


# ─── Balance Integration Tests ────────────────────────────────────────────────

class BalanceIntegrationTests(APITestCase):
    def setUp(self):
        self.a = mk_user("bi_a@x.com")
        self.b = mk_user("bi_b@x.com")
        self.group = mk_group(self.a)
        add_member(self.group, self.b)

    def _create(self, amount="100.00"):
        r = self.client.post(list_url(self.group.pk), {
            "description": "D",
            "amount": amount,
            "split_type": "equal",
            "splits": [{"user_id": self.a.id}, {"user_id": self.b.id}],
        }, format="json", **auth(self.a))
        return r.json()["id"]

    def test_balance_created_after_expense(self):
        self._create()
        self.assertEqual(Balance.objects.filter(group=self.group).count(), 1)

    def test_balance_reversed_after_delete(self):
        eid = self._create()
        before = abs(net_balance(self.group, self.a, self.b))
        self.client.delete(delete_url(self.group.pk, eid), **auth(self.a))
        after = abs(net_balance(self.group, self.a, self.b))
        self.assertEqual(after, before - D("50.00"))

    def test_balance_updated_after_edit(self):
        eid = self._create("100.00")
        # Edit to change amount and participants to only A (no balance entry)
        self.client.patch(
            edit_url(self.group.pk, eid), {
                "amount": "60.00",
                "split_type": "equal",
                "splits": [{"user_id": self.a.id}, {"user_id": self.b.id}],
            }, format="json", **auth(self.a)
        )
        self.assertEqual(abs(net_balance(self.group, self.a, self.b)), D("30.00"))


# ─── Cross-Group Isolation Tests ──────────────────────────────────────────────

class CrossGroupIsolationTests(APITestCase):
    def setUp(self):
        self.a = mk_user("cgi_a@x.com")
        self.b = mk_user("cgi_b@x.com")
        self.group1 = mk_group(self.a)
        self.group2 = mk_group(self.b)
        add_member(self.group1, self.b)
        add_member(self.group2, self.a)

    def test_expenses_of_group1_not_in_group2_list(self):
        self.client.post(list_url(self.group1.pk), {
            "description": "G1 Expense",
            "amount": "50.00",
            "split_type": "equal",
            "splits": [{"user_id": self.a.id}],
        }, format="json", **auth(self.a))

        r = self.client.get(list_url(self.group2.pk), **auth(self.a))
        self.assertEqual(r.json()["count"], 0)

    def test_balances_isolated_per_group(self):
        self.client.post(list_url(self.group1.pk), {
            "description": "G1",
            "amount": "80.00",
            "split_type": "equal",
            "splits": [{"user_id": self.a.id}, {"user_id": self.b.id}],
        }, format="json", **auth(self.a))

        self.assertEqual(Balance.objects.filter(group=self.group2).count(), 0)

    def test_nonexistent_group_404(self):
        r = self.client.get(list_url(99999), **auth(self.a))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
