"""
Groups app models: Group, GroupMembership, GroupInvitation.

Soft-delete strategy:
  Group          — is_deleted=True (never hard-deleted)
  GroupMembership — is_active=False + left_at timestamp
  GroupInvitation — status field transitions (pending → accepted/declined/expired)
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Group(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_groups",
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "groups"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "is_deleted"], name="group_creator_deleted_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def soft_delete(self) -> None:
        """Mark group as deleted without removing the row."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])


class GroupMembership(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_MEMBER, "Member"),
    ]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "group_memberships"
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_group_user_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "is_active"], name="membership_group_active_idx"),
            models.Index(fields=["user", "is_active"], name="membership_user_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.group} ({self.role})"

    def deactivate(self) -> None:
        """Remove a member from the group (soft removal)."""
        self.is_active = False
        self.left_at = timezone.now()
        self.save(update_fields=["is_active", "left_at"])


class GroupInvitation(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_EXPIRED, "Expired"),
    ]

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField(db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "group_invitations"
        ordering = ["-created_at"]
        constraints = [
            # Only one pending invitation per (group, email) at a time.
            # Expired/accepted/declined invitations do not block re-inviting.
            models.UniqueConstraint(
                fields=["group", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invitation_per_group_email",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "status"], name="invitation_group_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Invite {self.email} → {self.group} [{self.status}]"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
