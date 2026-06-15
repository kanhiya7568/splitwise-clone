"""
Settlement service layer.

All business logic for settlement operations lives here.
Views call services; views never implement business logic.

Integration with Balance Engine (Module 7):
  create_settlement  → apply_settlement_to_balances()
  update_settlement  → reverse old + apply new (atomic)
  delete_settlement  → reverse_settlement_from_balances()
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

from apps.balances.services import (
    apply_settlement_to_balances,
    reverse_settlement_from_balances,
)
from apps.groups.models import Group, GroupMembership
from apps.settlements.models import Settlement

User = get_user_model()


class SettlementServiceError(Exception):
    """Business rule violation — views convert to HTTP 400."""
    pass


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _require_active_member(group: Group, user) -> None:
    if not GroupMembership.objects.filter(group=group, user=user, is_active=True).exists():
        raise PermissionDenied("You must be an active member of this group.")


def _require_participant(settlement: Settlement, user) -> None:
    """Only payer or receiver may edit/delete a settlement."""
    if user.id not in (settlement.payer_id, settlement.receiver_id):
        raise PermissionDenied("Only the payer or receiver can modify this settlement.")


def _validate_participants(group: Group, payer_id: int, receiver_id: int) -> None:
    if payer_id == receiver_id:
        raise SettlementServiceError("Payer and receiver must be different users.")
    active_ids = set(
        GroupMembership.objects.filter(group=group, is_active=True)
        .values_list("user_id", flat=True)
    )
    missing = {payer_id, receiver_id} - active_ids
    if missing:
        raise SettlementServiceError(
            f"User IDs {sorted(missing)} are not active members of this group."
        )


# ─── create_settlement ────────────────────────────────────────────────────────

@transaction.atomic
def create_settlement(
    group: Group,
    created_by,
    payer_id: int,
    receiver_id: int,
    amount: Decimal,
    note: str = "",
) -> Settlement:
    """
    Record a settlement payment and update balances.

    Args:
        group:       The group this settlement belongs to.
        created_by:  Requesting authenticated user.
        payer_id:    User ID making the payment.
        receiver_id: User ID receiving the payment.
        amount:      Payment amount (must be > 0).
        note:        Optional note.

    Returns:
        The created Settlement.

    Raises:
        PermissionDenied:       created_by is not an active group member.
        SettlementServiceError: Validation failure.
    """
    _require_active_member(group, created_by)
    _validate_participants(group, payer_id, receiver_id)

    settlement = Settlement.objects.create(
        group=group,
        payer_id=payer_id,
        receiver_id=receiver_id,
        created_by=created_by,
        amount=amount,
        note=note,
    )
    apply_settlement_to_balances(settlement)
    return settlement


# ─── update_settlement ────────────────────────────────────────────────────────

@transaction.atomic
def update_settlement(
    settlement: Settlement,
    requesting_user,
    amount: Decimal = None,
    note: str = None,
) -> Settlement:
    """
    Edit a settlement: reverse old balance impact, apply updated impact.

    Only the payer or receiver may edit.
    All operations are atomic — if balance update fails, the edit is rolled back.

    Args:
        settlement:      The Settlement to update.
        requesting_user: Must be payer or receiver.
        amount:          New amount (optional).
        note:            New note (optional).

    Returns:
        Updated Settlement.
    """
    if settlement.is_deleted:
        raise SettlementServiceError("Cannot edit a deleted settlement.")

    _require_participant(settlement, requesting_user)

    # Reverse old balance impact before changing the amount
    reverse_settlement_from_balances(settlement)

    update_fields = ["updated_at"]
    if amount is not None:
        settlement.amount = amount
        update_fields.append("amount")
    if note is not None:
        settlement.note = note
        update_fields.append("note")

    settlement.save(update_fields=update_fields)

    # Apply new balance impact
    apply_settlement_to_balances(settlement)
    return settlement


# ─── delete_settlement ────────────────────────────────────────────────────────

@transaction.atomic
def delete_settlement(settlement: Settlement, requesting_user) -> Settlement:
    """
    Soft-delete a settlement and reverse its balance impact.

    Only the payer or receiver may delete.

    Args:
        settlement:      The Settlement to delete.
        requesting_user: Must be payer or receiver.

    Returns:
        Soft-deleted Settlement.
    """
    if settlement.is_deleted:
        raise SettlementServiceError("This settlement has already been deleted.")

    _require_participant(settlement, requesting_user)

    reverse_settlement_from_balances(settlement)
    settlement.soft_delete()
    return settlement


# ─── get_settlement_history ───────────────────────────────────────────────────

def get_settlement_history(group: Group, requesting_user, include_deleted: bool = False):
    """
    Return a QuerySet of settlements for a group.

    Only active group members may view history.

    Args:
        group:            The Group to query.
        requesting_user:  Must be an active group member.
        include_deleted:  If True, include soft-deleted settlements (admin use).

    Returns:
        QuerySet ordered by -created_at.
    """
    _require_active_member(group, requesting_user)

    qs = (
        Settlement.objects
        .filter(group=group)
        .select_related("payer", "receiver", "created_by")
        .order_by("-created_at")
    )
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs
