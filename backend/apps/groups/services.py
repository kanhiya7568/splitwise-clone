"""
Group service layer.

All business logic for group operations lives here.
Views call services — views never contain business logic directly.

Raises:
    GroupServiceError — for business rule violations (caught by views → 400/403)
    django.core.exceptions.PermissionDenied — for authorization failures (→ 403)
    django.http.Http404 — for missing resources (→ 404)
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.groups.models import Group, GroupInvitation, GroupMembership

User = get_user_model()


class GroupServiceError(Exception):
    """Raised when a business rule is violated. Views convert this to HTTP 400."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_active_membership(group: Group, user) -> GroupMembership:
    """Return active membership or raise Http404."""
    try:
        return GroupMembership.objects.get(group=group, user=user, is_active=True)
    except GroupMembership.DoesNotExist:
        raise Http404("Membership not found.")


def _require_admin(group: Group, user) -> GroupMembership:
    """Return membership if user is active admin, else raise PermissionDenied."""
    try:
        membership = GroupMembership.objects.get(
            group=group, user=user, is_active=True, role=GroupMembership.ROLE_ADMIN
        )
        return membership
    except GroupMembership.DoesNotExist:
        raise PermissionDenied("Only group admins can perform this action.")


def _active_admin_count(group: Group) -> int:
    return GroupMembership.objects.filter(
        group=group, is_active=True, role=GroupMembership.ROLE_ADMIN
    ).count()


# ─────────────────────────────────────────────────────────────────────────────
# create_group
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_group(user, name: str, description: str = "") -> Group:
    """
    Create a new group and add the creator as the sole admin.

    Args:
        user:        The authenticated user creating the group.
        name:        Group display name (validated by serializer).
        description: Optional description.

    Returns:
        The newly created Group instance with membership prefetched.
    """
    group = Group.objects.create(
        name=name,
        description=description,
        created_by=user,
    )
    GroupMembership.objects.create(
        group=group,
        user=user,
        role=GroupMembership.ROLE_ADMIN,
    )
    return group


# ─────────────────────────────────────────────────────────────────────────────
# invite_user
# ─────────────────────────────────────────────────────────────────────────────

INVITATION_TTL_DAYS = 7


@transaction.atomic
def invite_user(group: Group, email: str, invited_by) -> dict:
    """
    Invite a user to a group by email.

    Behaviour:
        - If a user with that email exists and is already an active member → raise error.
        - If a user with that email exists and was previously removed → re-activate membership.
        - If a user with that email exists and has no prior membership → add as member.
        - If no user with that email exists → create a pending GroupInvitation.

    Args:
        group:      The Group to invite into.
        email:      Target email address (already normalised by serializer).
        invited_by: The requesting User.

    Returns:
        dict with keys 'action' ('added' | 'reinvited' | 'invited') and
        either 'membership' or 'invitation'.

    Raises:
        GroupServiceError: If user is already an active member or a pending
                           invitation already exists for this email.
    """
    # ── Case 1: User already registered ──────────────────────────────────────
    try:
        target_user = User.objects.get(email=email)
    except User.DoesNotExist:
        target_user = None

    if target_user is not None:
        membership = GroupMembership.objects.filter(
            group=group, user=target_user
        ).first()

        if membership is not None:
            if membership.is_active:
                raise GroupServiceError(
                    f"{email} is already an active member of this group."
                )
            # Previously removed — re-activate
            membership.is_active = True
            membership.left_at = None
            membership.save(update_fields=["is_active", "left_at"])
            # Cancel any pending invitation for this email
            GroupInvitation.objects.filter(
                group=group, email=email, status=GroupInvitation.STATUS_PENDING
            ).update(status=GroupInvitation.STATUS_ACCEPTED)
            return {"action": "readded", "membership": membership}

        # No prior membership — add fresh
        membership = GroupMembership.objects.create(
            group=group,
            user=target_user,
            role=GroupMembership.ROLE_MEMBER,
        )
        GroupInvitation.objects.filter(
            group=group, email=email, status=GroupInvitation.STATUS_PENDING
        ).update(status=GroupInvitation.STATUS_ACCEPTED)
        return {"action": "added", "membership": membership}

    # ── Case 2: User not registered — create pending invitation ──────────────
    if GroupInvitation.objects.filter(
        group=group, email=email, status=GroupInvitation.STATUS_PENDING
    ).exists():
        raise GroupServiceError(
            f"A pending invitation already exists for {email}."
        )

    invitation = GroupInvitation.objects.create(
        group=group,
        email=email,
        invited_by=invited_by,
        status=GroupInvitation.STATUS_PENDING,
        expires_at=timezone.now() + timedelta(days=INVITATION_TTL_DAYS),
    )
    return {"action": "invited", "invitation": invitation}


# ─────────────────────────────────────────────────────────────────────────────
# remove_member
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def remove_member(group: Group, target_user_id: int, requesting_user) -> GroupMembership:
    """
    Remove a member from a group (soft removal — is_active=False).

    Rules:
        - Requesting user must be an active admin.
        - Target user must be an active member.
        - An admin cannot remove themselves if they are the only admin.

    Args:
        group:             The Group to remove from.
        target_user_id:    PK of the user to remove.
        requesting_user:   The authenticated requesting User.

    Returns:
        The deactivated GroupMembership.

    Raises:
        PermissionDenied:  Requesting user is not an admin.
        Http404:           Target user is not an active member.
        GroupServiceError: Admin cannot remove themselves as the only admin.
    """
    _require_admin(group, requesting_user)

    # Fetch target membership
    try:
        target_membership = GroupMembership.objects.get(
            group=group, user_id=target_user_id, is_active=True
        )
    except GroupMembership.DoesNotExist:
        raise Http404("The specified user is not an active member of this group.")

    # Guard: cannot remove self if sole admin
    if target_user_id == requesting_user.id:
        if _active_admin_count(group) <= 1:
            raise GroupServiceError(
                "You are the only admin. Assign another admin before removing yourself."
            )

    target_membership.deactivate()
    return target_membership


# ─────────────────────────────────────────────────────────────────────────────
# update_group
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def update_group(group: Group, requesting_user, name: str = None, description: str = None) -> Group:
    """
    Update group name and/or description. Only admins may do this.

    Args:
        group:            The Group to update.
        requesting_user:  Must be an active admin.
        name:             New name (optional).
        description:      New description (optional).

    Returns:
        The updated Group.
    """
    _require_admin(group, requesting_user)
    update_fields = ["updated_at"]

    if name is not None:
        group.name = name
        update_fields.append("name")
    if description is not None:
        group.description = description
        update_fields.append("description")

    group.save(update_fields=update_fields)
    return group


# ─────────────────────────────────────────────────────────────────────────────
# delete_group
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def delete_group(group: Group, requesting_user) -> Group:
    """
    Soft-delete a group.

    Rules:
        - Only an active admin can delete the group.
        - Deletion is blocked if any unsettled balances exist (net_amount ≠ 0).

    Args:
        group:           The Group to delete.
        requesting_user: Must be an active admin.

    Returns:
        The soft-deleted Group.

    Raises:
        PermissionDenied:  Not an admin.
        GroupServiceError: Unsettled balances exist.
    """
    _require_admin(group, requesting_user)

    # Lazy import to avoid circular dependency (balances app imports groups)
    from apps.balances.models import Balance

    unsettled = (
        Balance.objects.filter(group=group)
        .exclude(net_amount=0)
        .exists()
    )
    if unsettled:
        raise GroupServiceError(
            "Cannot delete a group with unsettled balances. "
            "Settle all debts before deleting."
        )

    group.soft_delete()
    return group
