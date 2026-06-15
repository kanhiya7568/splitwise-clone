"""
Group API tests — Module 4.

Covers all endpoints and edge cases including:
  - Create group (creator becomes admin)
  - List groups (only user's groups visible)
  - Retrieve group (member access, non-member blocked)
  - Update group (admin only, member blocked)
  - Delete group (admin only, settled balances required)
  - Invite by email (existing user, non-existing user, re-add, duplicate pending)
  - Remove member (admin can, member cannot, last-admin guard)

Run with:
    python manage.py test apps.groups
"""

from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.balances.models import Balance
from apps.groups.models import Group, GroupInvitation, GroupMembership
from apps.users.models import User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_user(email="u@example.com", **kw) -> User:
    return User.objects.create_user(
        email=email, password="Pass1word", first_name="T", last_name="U", **kw
    )


def auth_header(user: User) -> dict:
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def make_group(creator: User, name="Test Group") -> Group:
    from apps.groups.services import create_group
    return create_group(user=creator, name=name)


def add_member(group: Group, user: User, role=GroupMembership.ROLE_MEMBER) -> GroupMembership:
    return GroupMembership.objects.create(group=group, user=user, role=role)


# ─────────────────────────────────────────────────────────────────────────────
# Create Group
# ─────────────────────────────────────────────────────────────────────────────

class CreateGroupTests(APITestCase):
    def setUp(self):
        self.user = make_user("creator@example.com")
        self.url = reverse("group_list_create")

    def test_create_group_success_201(self):
        r = self.client.post(self.url, {"name": "Roomies"}, format="json", **auth_header(self.user))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_create_group_returns_group_data(self):
        r = self.client.post(self.url, {"name": "Roomies"}, format="json", **auth_header(self.user))
        self.assertEqual(r.json()["name"], "Roomies")

    def test_creator_becomes_admin(self):
        r = self.client.post(self.url, {"name": "Trip"}, format="json", **auth_header(self.user))
        group_id = r.json()["id"]
        membership = GroupMembership.objects.get(group_id=group_id, user=self.user)
        self.assertEqual(membership.role, GroupMembership.ROLE_ADMIN)

    def test_creator_is_active_member(self):
        r = self.client.post(self.url, {"name": "Trip"}, format="json", **auth_header(self.user))
        group_id = r.json()["id"]
        self.assertTrue(
            GroupMembership.objects.filter(group_id=group_id, user=self.user, is_active=True).exists()
        )

    def test_create_group_unauthenticated_401(self):
        r = self.client.post(self.url, {"name": "X"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_group_blank_name_400(self):
        r = self.client.post(self.url, {"name": "  "}, format="json", **auth_header(self.user))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_group_missing_name_400(self):
        r = self.client.post(self.url, {}, format="json", **auth_header(self.user))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_group_with_description(self):
        r = self.client.post(
            self.url, {"name": "G", "description": "Desc"}, format="json", **auth_header(self.user)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["description"], "Desc")

    def test_member_count_one_after_create(self):
        r = self.client.post(self.url, {"name": "Solo"}, format="json", **auth_header(self.user))
        self.assertEqual(r.json()["member_count"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# List Groups
# ─────────────────────────────────────────────────────────────────────────────

class ListGroupsTests(APITestCase):
    def setUp(self):
        self.user = make_user("lister@example.com")
        self.other = make_user("other@example.com")
        self.url = reverse("group_list_create")
        self.my_group = make_group(self.user, "My Group")
        self.other_group = make_group(self.other, "Other Group")

    def test_list_returns_only_user_groups(self):
        r = self.client.get(self.url, **auth_header(self.user))
        self.assertEqual(r.status_code, 200)
        names = [g["name"] for g in r.json()["results"]]
        self.assertIn("My Group", names)
        self.assertNotIn("Other Group", names)

    def test_list_includes_groups_user_was_invited_to(self):
        add_member(self.other_group, self.user)
        r = self.client.get(self.url, **auth_header(self.user))
        names = [g["name"] for g in r.json()["results"]]
        self.assertIn("Other Group", names)

    def test_deleted_groups_not_listed(self):
        self.my_group.soft_delete()
        r = self.client.get(self.url, **auth_header(self.user))
        names = [g["name"] for g in r.json()["results"]]
        self.assertNotIn("My Group", names)

    def test_list_unauthenticated_401(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieve Group
# ─────────────────────────────────────────────────────────────────────────────

class RetrieveGroupTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com")
        self.member = make_user("member@example.com")
        self.outsider = make_user("outsider@example.com")
        self.group = make_group(self.admin)
        add_member(self.group, self.member)

    def url(self):
        return reverse("group_detail", kwargs={"pk": self.group.pk})

    def test_admin_can_retrieve_200(self):
        r = self.client.get(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)

    def test_member_can_retrieve_200(self):
        r = self.client.get(self.url(), **auth_header(self.member))
        self.assertEqual(r.status_code, 200)

    def test_outsider_gets_403(self):
        r = self.client.get(self.url(), **auth_header(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_group_404(self):
        r = self.client.get(reverse("group_detail", kwargs={"pk": 99999}), **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_contains_members_list(self):
        r = self.client.get(self.url(), **auth_header(self.admin))
        data = r.json()
        self.assertIn("members", data)
        emails = [m["user"]["email"] for m in data["members"]]
        self.assertIn("admin@example.com", emails)
        self.assertIn("member@example.com", emails)


# ─────────────────────────────────────────────────────────────────────────────
# Update Group (rename / update description)
# ─────────────────────────────────────────────────────────────────────────────

class UpdateGroupTests(APITestCase):
    def setUp(self):
        self.admin = make_user("upd_admin@example.com")
        self.member = make_user("upd_member@example.com")
        self.group = make_group(self.admin, "Old Name")
        add_member(self.group, self.member)

    def url(self):
        return reverse("group_update", kwargs={"pk": self.group.pk})

    def test_admin_can_rename_200(self):
        r = self.client.patch(self.url(), {"name": "New Name"}, format="json", **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "New Name")

    def test_admin_can_update_description(self):
        r = self.client.patch(
            self.url(), {"description": "Updated"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["description"], "Updated")

    def test_member_cannot_rename_403(self):
        r = self.client.patch(self.url(), {"name": "Hack"}, format="json", **auth_header(self.member))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_rename_403(self):
        outsider = make_user("outsider2@example.com")
        r = self.client.patch(self.url(), {"name": "Hack"}, format="json", **auth_header(outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_blank_name_returns_400(self):
        r = self.client.patch(self.url(), {"name": ""}, format="json", **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_body_returns_400(self):
        r = self.client.patch(self.url(), {}, format="json", **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# Delete Group
# ─────────────────────────────────────────────────────────────────────────────

class DeleteGroupTests(APITestCase):
    def setUp(self):
        self.admin = make_user("del_admin@example.com")
        self.member = make_user("del_member@example.com")
        self.group = make_group(self.admin)
        add_member(self.group, self.member)

    def url(self):
        return reverse("group_delete", kwargs={"pk": self.group.pk})

    def test_admin_can_delete_settled_group_200(self):
        r = self.client.delete(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)
        self.group.refresh_from_db()
        self.assertTrue(self.group.is_deleted)

    def test_member_cannot_delete_403(self):
        r = self.client.delete(self.url(), **auth_header(self.member))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_deleted)

    def test_delete_with_unsettled_balance_400(self):
        # Create unsettled balance
        Balance.objects.create(
            group=self.group,
            user1=self.admin if self.admin.id < self.member.id else self.member,
            user2=self.member if self.admin.id < self.member.id else self.admin,
            net_amount=Decimal("50.00"),
        )
        r = self.client.delete(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unsettled", r.json()["error"].lower())

    def test_delete_nonexistent_group_404(self):
        r = self.client.delete(
            reverse("group_delete", kwargs={"pk": 99999}), **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_with_zero_balance_succeeds(self):
        """Zero-balance row should not block deletion."""
        u1, u2 = (self.admin, self.member) if self.admin.id < self.member.id else (self.member, self.admin)
        Balance.objects.create(group=self.group, user1=u1, user2=u2, net_amount=Decimal("0.00"))
        r = self.client.delete(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# Invite User
# ─────────────────────────────────────────────────────────────────────────────

class InviteUserTests(APITestCase):
    def setUp(self):
        self.admin = make_user("inv_admin@example.com")
        self.group = make_group(self.admin)

    def url(self):
        return reverse("group_invite", kwargs={"pk": self.group.pk})

    def test_invite_existing_user_adds_as_member(self):
        existing = make_user("existing@example.com")
        r = self.client.post(
            self.url(), {"email": "existing@example.com"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["action"], "added")
        self.assertTrue(
            GroupMembership.objects.filter(group=self.group, user=existing, is_active=True).exists()
        )

    def test_invite_nonexistent_user_creates_pending_invitation(self):
        r = self.client.post(
            self.url(), {"email": "unknown@example.com"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["action"], "invited")
        self.assertTrue(
            GroupInvitation.objects.filter(
                group=self.group, email="unknown@example.com", status="pending"
            ).exists()
        )

    def test_invite_already_active_member_400(self):
        already = make_user("already@example.com")
        add_member(self.group, already)
        r = self.client.post(
            self.url(), {"email": "already@example.com"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_pending_invitation_400(self):
        self.client.post(
            self.url(), {"email": "ghost@example.com"}, format="json", **auth_header(self.admin)
        )
        r = self.client.post(
            self.url(), {"email": "ghost@example.com"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_email_case_insensitive(self):
        """Inviting UPPER@example.com should match existing user upper@example.com."""
        existing = make_user("upper@example.com")
        r = self.client.post(
            self.url(), {"email": "UPPER@EXAMPLE.COM"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["action"], "added")

    def test_readd_previously_removed_user(self):
        removed = make_user("removed@example.com")
        m = add_member(self.group, removed)
        m.deactivate()
        r = self.client.post(
            self.url(), {"email": "removed@example.com"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["action"], "readded")
        m.refresh_from_db()
        self.assertTrue(m.is_active)

    def test_invite_invalid_email_400(self):
        r = self.client.post(
            self.url(), {"email": "not-an-email"}, format="json", **auth_header(self.admin)
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_nonexistent_group_404(self):
        r = self.client.post(
            reverse("group_invite", kwargs={"pk": 99999}),
            {"email": "x@example.com"},
            format="json",
            **auth_header(self.admin),
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# Remove Member
# ─────────────────────────────────────────────────────────────────────────────

class RemoveMemberTests(APITestCase):
    def setUp(self):
        self.admin = make_user("rem_admin@example.com")
        self.member = make_user("rem_member@example.com")
        self.outsider = make_user("rem_outsider@example.com")
        self.group = make_group(self.admin)
        self.membership = add_member(self.group, self.member)

    def url(self, uid=None):
        return reverse(
            "group_remove_member",
            kwargs={"pk": self.group.pk, "uid": uid or self.member.pk},
        )

    def test_admin_can_remove_member_200(self):
        r = self.client.delete(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.is_active)

    def test_removed_member_has_left_at_set(self):
        self.client.delete(self.url(), **auth_header(self.admin))
        self.membership.refresh_from_db()
        self.assertIsNotNone(self.membership.left_at)

    def test_member_cannot_remove_another_member_403(self):
        third = make_user("third@example.com")
        add_member(self.group, third)
        url = reverse("group_remove_member", kwargs={"pk": self.group.pk, "uid": third.pk})
        r = self.client.delete(url, **auth_header(self.member))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_outsider_cannot_remove_member_403(self):
        r = self.client.delete(self.url(), **auth_header(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_remove_self_as_only_admin_400(self):
        url = reverse("group_remove_member", kwargs={"pk": self.group.pk, "uid": self.admin.pk})
        r = self.client.delete(url, **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only admin", r.json()["error"].lower())

    def test_admin_can_remove_self_if_another_admin_exists(self):
        second_admin = make_user("second_admin@example.com")
        add_member(self.group, second_admin, role=GroupMembership.ROLE_ADMIN)
        url = reverse("group_remove_member", kwargs={"pk": self.group.pk, "uid": self.admin.pk})
        r = self.client.delete(url, **auth_header(self.admin))
        self.assertEqual(r.status_code, 200)

    def test_remove_already_removed_member_404(self):
        self.membership.deactivate()
        r = self.client.delete(self.url(), **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_nonexistent_user_404(self):
        r = self.client.delete(self.url(uid=99999), **auth_header(self.admin))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_historical_record_preserved_after_removal(self):
        """Soft-deleted membership row must still exist in DB."""
        self.client.delete(self.url(), **auth_header(self.admin))
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, user=self.member
            ).exists()
        )


# ─────────────────────────────────────────────────────────────────────────────
# List Members
# ─────────────────────────────────────────────────────────────────────────────

class ListMembersTests(APITestCase):
    def setUp(self):
        self.admin = make_user("lm_admin@example.com")
        self.member = make_user("lm_member@example.com")
        self.outsider = make_user("lm_outsider@example.com")
        self.group = make_group(self.admin)
        add_member(self.group, self.member)

    def url(self):
        return reverse("group_members", kwargs={"pk": self.group.pk})

    def test_member_can_list_200(self):
        r = self.client.get(self.url(), **auth_header(self.member))
        self.assertEqual(r.status_code, 200)

    def test_outsider_gets_403(self):
        r = self.client.get(self.url(), **auth_header(self.outsider))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_removed_member_not_in_list(self):
        removed = make_user("lm_removed@example.com")
        m = add_member(self.group, removed)
        m.deactivate()
        r = self.client.get(self.url(), **auth_header(self.admin))
        emails = [item["user"]["email"] for item in r.json()["results"]]
        self.assertNotIn("lm_removed@example.com", emails)
