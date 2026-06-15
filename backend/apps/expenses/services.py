"""
Expense service layer.

All business logic for expense operations lives here.
Views call services — views never implement business logic directly.

Architecture note:
  Balance updates are intentionally omitted in Module 5A.
  Each function has a clearly marked stub where Module 7 (Balance service)
  will insert its call. The stub is wrapped in the same transaction.atomic()
  so balance updates will be atomic with the expense write.

Raises:
    ExpenseServiceError      — business rule violation (→ HTTP 400)
    django.core.exceptions.PermissionDenied — authorization failure (→ HTTP 403)
    django.http.Http404      — resource not found (→ HTTP 404)
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

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
from apps.groups.models import Group, GroupMembership

User = get_user_model()


class ExpenseServiceError(Exception):
    """Raised when a business rule is violated. Views convert to HTTP 400."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_active_member(group: Group, user) -> GroupMembership:
    """Return active membership or raise PermissionDenied."""
    try:
        return GroupMembership.objects.get(group=group, user=user, is_active=True)
    except GroupMembership.DoesNotExist:
        raise PermissionDenied("You must be an active member of this group.")


def _require_edit_permission(expense: Expense, requesting_user) -> None:
    """
    Expense editing is allowed if the requesting user is:
      - The creator of the expense, OR
      - An active admin of the expense's group

    Raises:
        PermissionDenied: If neither condition is met.
    """
    if expense.created_by_id == requesting_user.id:
        return
    is_admin = GroupMembership.objects.filter(
        group=expense.group,
        user=requesting_user,
        is_active=True,
        role=GroupMembership.ROLE_ADMIN,
    ).exists()
    if not is_admin:
        raise PermissionDenied(
            "Only the expense creator or a group admin can modify this expense."
        )


def _compute_splits(
    split_type: str,
    total: Decimal,
    splits_input: list[dict],
    participant_ids: list[int],
    payer_id: int,
) -> list[dict]:
    """
    Route to the correct split calculator based on split_type.
    Returns a list of normalised split dicts ready for DB insertion.

    Raises:
        ExpenseServiceError: wrapping any ExpenseValidationError.
    """
    try:
        if split_type == Expense.SPLIT_EQUAL:
            return calculate_equal_splits(total, participant_ids, payer_id)
        elif split_type == Expense.SPLIT_UNEQUAL:
            return validate_unequal_splits(total, splits_input)
        elif split_type == Expense.SPLIT_PERCENTAGE:
            return validate_percentage_splits(total, splits_input)
        elif split_type == Expense.SPLIT_SHARES:
            return validate_shares_splits(total, splits_input)
        else:
            raise ExpenseServiceError(f"Unknown split type: {split_type}.")
    except ExpenseValidationError as exc:
        raise ExpenseServiceError(str(exc)) from exc


def _create_split_rows(expense: Expense, splits: list[dict]) -> list[ExpenseSplit]:
    """Bulk-create ExpenseSplit rows. Must be called inside a transaction."""
    rows = [
        ExpenseSplit(
            expense=expense,
            user_id=s["user_id"],
            amount=s["amount"],
            percentage=s.get("percentage"),
            shares=s.get("shares"),
        )
        for s in splits
    ]
    return ExpenseSplit.objects.bulk_create(rows)


def _validate_common(
    group: Group,
    paid_by_id: int,
    split_type: str,
    total: Decimal,
    splits_input: list[dict],
    participant_ids: list[int],
) -> list[dict]:
    """
    Run all validations common to create and update:
      1. Payer is an active group member.
      2. All participants are active group members.
      3. No duplicate participants.
      4. Payer is a participant.
      5. Split amounts/percentages/shares are valid.

    Returns normalised split data.
    """
    # 1 — Payer must be a group member
    if not GroupMembership.objects.filter(
        group=group, user_id=paid_by_id, is_active=True
    ).exists():
        raise ExpenseServiceError("The payer must be an active member of the group.")

    # 2 — All participants must be active group members
    try:
        validate_participants_are_group_members(group, participant_ids)
    except ExpenseValidationError as exc:
        raise ExpenseServiceError(str(exc)) from exc

    # 3 — No duplicate participants
    try:
        validate_no_duplicate_participants(participant_ids)
    except ExpenseValidationError as exc:
        raise ExpenseServiceError(str(exc)) from exc

    # 4 — Payer must be in participants
    try:
        validate_payer_is_participant(paid_by_id, participant_ids)
    except ExpenseValidationError as exc:
        raise ExpenseServiceError(str(exc)) from exc

    # 5 — Split calculation
    return _compute_splits(split_type, total, splits_input, participant_ids, paid_by_id)


# ─────────────────────────────────────────────────────────────────────────────
# create_expense
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def create_expense(
    group: Group,
    created_by,
    paid_by_id: int,
    description: str,
    amount: Decimal,
    category: str,
    expense_date: date,
    split_type: str,
    splits_input: list[dict],
    participant_ids: list[int],
) -> tuple[Expense, list[ExpenseSplit]]:
    """
    Create an expense and its splits inside a single atomic transaction.

    Args:
        group:           The group this expense belongs to.
        created_by:      The authenticated user creating the expense.
        paid_by_id:      User ID of whoever physically paid.
        description:     Short description of the expense.
        amount:          Total monetary amount (Decimal).
        category:        One of Expense.CATEGORY_* constants.
        expense_date:    Date the expense occurred.
        split_type:      One of Expense.SPLIT_* constants.
        splits_input:    For non-equal splits: [{user_id, amount/percentage/shares}].
                         For equal splits: not used (pass [] or None).
        participant_ids: List of user IDs being split across. Must include payer.

    Returns:
        (Expense, [ExpenseSplit]) — the created expense and its split rows.

    Raises:
        PermissionDenied:    created_by is not an active group member.
        ExpenseServiceError: Any validation rule violation.
    """
    # Requesting user must be an active group member to create expenses
    _require_active_member(group, created_by)

    # Run all validations and compute split amounts
    splits = _validate_common(
        group, paid_by_id, split_type, amount, splits_input, participant_ids
    )

    # Write expense
    expense = Expense.objects.create(
        group=group,
        paid_by_id=paid_by_id,
        created_by=created_by,
        description=description,
        amount=amount,
        category=category,
        expense_date=expense_date,
        split_type=split_type,
    )

    # Write splits
    split_rows = _create_split_rows(expense, splits)

    from apps.balances.services import apply_expense_to_balances
    apply_expense_to_balances(expense, split_rows)

    return expense, split_rows


# ─────────────────────────────────────────────────────────────────────────────
# update_expense
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def update_expense(
    expense: Expense,
    requesting_user,
    paid_by_id: int = None,
    description: str = None,
    amount: Decimal = None,
    category: str = None,
    expense_date: date = None,
    split_type: str = None,
    splits_input: list[dict] = None,
    participant_ids: list[int] = None,
) -> tuple[Expense, list[ExpenseSplit]]:
    """
    Update an existing expense and recompute its splits.

    Strategy:
      - Delete old splits (they will be recreated from scratch).
      - Re-validate all fields using current or updated values.
      - Recompute and insert new splits.
      - Balance reversal + reapplication hook (Module 7).

    Permission: creator OR active group admin.

    Args:
        expense:       The Expense to update.
        requesting_user: Must be creator or group admin.
        All other args: Optional; if None, existing value is preserved.

    Returns:
        (Expense, [ExpenseSplit]) — updated expense and new splits.
    """
    _require_edit_permission(expense, requesting_user)

    # Resolve effective values (merge new with existing)
    eff_paid_by_id    = paid_by_id    if paid_by_id    is not None else expense.paid_by_id
    eff_description   = description   if description   is not None else expense.description
    eff_amount        = amount        if amount        is not None else expense.amount
    eff_category      = category      if category      is not None else expense.category
    eff_expense_date  = expense_date  if expense_date  is not None else expense.expense_date
    eff_split_type    = split_type    if split_type    is not None else expense.split_type
    eff_splits_input  = splits_input  if splits_input  is not None else []
    eff_participant_ids = (
        participant_ids if participant_ids is not None
        else list(expense.splits.values_list("user_id", flat=True))
    )

    # Validate and compute new splits
    new_splits = _validate_common(
        expense.group,
        eff_paid_by_id,
        eff_split_type,
        eff_amount,
        eff_splits_input,
        eff_participant_ids,
    )

    from apps.balances.services import reverse_expense_from_balances
    old_splits = list(expense.splits.all())
    reverse_expense_from_balances(expense, old_splits)

    # Delete old splits (expense row is preserved and updated below)
    expense.splits.all().delete()

    # Update expense fields
    update_fields = ["updated_at"]
    if paid_by_id    is not None: expense.paid_by_id    = eff_paid_by_id;   update_fields.append("paid_by")
    if description   is not None: expense.description   = eff_description;  update_fields.append("description")
    if amount        is not None: expense.amount        = eff_amount;       update_fields.append("amount")
    if category      is not None: expense.category      = eff_category;     update_fields.append("category")
    if expense_date  is not None: expense.expense_date  = eff_expense_date; update_fields.append("expense_date")
    if split_type    is not None: expense.split_type    = eff_split_type;   update_fields.append("split_type")
    expense.save(update_fields=update_fields)

    # Insert new splits
    new_split_rows = _create_split_rows(expense, new_splits)

    from apps.balances.services import apply_expense_to_balances
    apply_expense_to_balances(expense, new_split_rows)

    return expense, new_split_rows


# ─────────────────────────────────────────────────────────────────────────────
# delete_expense
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def delete_expense(expense: Expense, requesting_user) -> Expense:
    """
    Soft-delete an expense.

    Splits are NOT deleted — they are retained for historical audit.
    Balance reversal hook is stubbed for Module 7.

    Permission: creator OR active group admin.

    Raises:
        PermissionDenied:    Not creator or admin.
        ExpenseServiceError: Expense is already deleted.
    """
    if expense.is_deleted:
        raise ExpenseServiceError("This expense has already been deleted.")

    _require_edit_permission(expense, requesting_user)

    from apps.balances.services import reverse_expense_from_balances
    reverse_expense_from_balances(expense, list(expense.splits.all()))

    expense.soft_delete()
    return expense


# ─────────────────────────────────────────────────────────────────────────────
# get_expense_history
# ─────────────────────────────────────────────────────────────────────────────

def get_expense_history(
    group: Group,
    requesting_user,
    category: str = None,
    paid_by_id: int = None,
    from_date: date = None,
    to_date: date = None,
):
    """
    Return a filtered QuerySet of active (non-deleted) expenses for a group.

    The requesting user must be an active group member.

    Args:
        group:           Group to query.
        requesting_user: Must be an active member.
        category:        Optional filter by Expense.CATEGORY_* value.
        paid_by_id:      Optional filter by who paid.
        from_date:       Optional filter: expense_date >= from_date.
        to_date:         Optional filter: expense_date <= to_date.

    Returns:
        QuerySet of Expense (not yet evaluated — caller applies pagination).
    """
    _require_active_member(group, requesting_user)

    qs = (
        Expense.objects
        .filter(group=group, is_deleted=False)
        .select_related("paid_by", "created_by")
        .prefetch_related("splits__user")
        .order_by("-expense_date", "-created_at")
    )

    if category:
        qs = qs.filter(category=category)
    if paid_by_id:
        qs = qs.filter(paid_by_id=paid_by_id)
    if from_date:
        qs = qs.filter(expense_date__gte=from_date)
    if to_date:
        qs = qs.filter(expense_date__lte=to_date)

    return qs
