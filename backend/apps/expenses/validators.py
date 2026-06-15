"""
Expense validators — pure functions, no DB access, no side effects.

All functions raise ExpenseValidationError (a plain Exception subclass)
so they can be called from both serializers and services.

Serializers catch ExpenseValidationError → reraise as serializers.ValidationError.
Services catch ExpenseValidationError → reraise as ExpenseServiceError.

Split type validation responsibilities:
  validate_equal_split       — validates participant list; calculates amounts
  validate_unequal_split     — validates amounts sum to total
  validate_percentage_split  — validates percentages sum to 100 (±0.01 tolerance)
  validate_shares_split      — validates total shares > 0; calculates amounts
  validate_participants      — validates all participant IDs are active group members
  validate_payer_is_participant — validates payer is in participants list
"""

from decimal import ROUND_DOWN, Decimal
from typing import Optional

from django.db.models import QuerySet

TWO_DP = Decimal("0.01")
PERCENTAGE_TOLERANCE = Decimal("0.01")  # ±0.01% allowed for rounding


class ExpenseValidationError(Exception):
    """
    Raised by validators when a business rule is violated.

    Callers convert this to their own error type:
      Serializers → serializers.ValidationError (→ HTTP 400)
      Services    → ExpenseServiceError (→ HTTP 400)
    """

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field  # Optional field name for serializer error detail


# ─────────────────────────────────────────────────────────────────────────────
# Participant validators
# ─────────────────────────────────────────────────────────────────────────────

def validate_participants_are_group_members(group, participant_ids: list[int]) -> None:
    """
    Verify all participant_ids are active members of the group.

    Raises:
        ExpenseValidationError: If any participant is not an active member.
    """
    from apps.groups.models import GroupMembership

    if not participant_ids:
        raise ExpenseValidationError("At least one participant is required.", field="splits")

    active_member_ids = set(
        GroupMembership.objects.filter(
            group=group, is_active=True
        ).values_list("user_id", flat=True)
    )

    invalid = set(participant_ids) - active_member_ids
    if invalid:
        raise ExpenseValidationError(
            f"The following user IDs are not active members of this group: {sorted(invalid)}.",
            field="splits",
        )


def validate_payer_is_participant(payer_id: int, participant_ids: list[int]) -> None:
    """
    The payer must be included in the participants list.
    Their split represents their own share (even if their balance impact is zero).

    Raises:
        ExpenseValidationError: If payer is not in participants.
    """
    if payer_id not in participant_ids:
        raise ExpenseValidationError(
            "The payer must be included in the expense participants.",
            field="paid_by",
        )


def validate_no_duplicate_participants(participant_ids: list[int]) -> None:
    """Reject duplicate user IDs in the participants list."""
    if len(participant_ids) != len(set(participant_ids)):
        seen = set()
        dups = [uid for uid in participant_ids if uid in seen or seen.add(uid)]
        raise ExpenseValidationError(
            f"Duplicate participants found: {dups}. Each user may appear only once.",
            field="splits",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Equal Split
# ─────────────────────────────────────────────────────────────────────────────

def calculate_equal_splits(
    total: Decimal,
    participant_ids: list[int],
    payer_id: int,
) -> list[dict]:
    """
    Divide total equally among all participants.

    Algorithm:
        base    = floor(total / n, 2dp)
        remainder = total - base * n   (always 0 ≤ remainder < $0.01 * n)
        payer's share = base + remainder

    The remainder is assigned to the payer because they physically hold the money
    and the rounding difference is smallest when assigned to one party.

    Returns:
        List of dicts: [{user_id, amount, percentage=None, shares=None}]
    """
    if not participant_ids:
        raise ExpenseValidationError("Participants list cannot be empty.", field="splits")

    n = len(participant_ids)
    base = (total / Decimal(n)).quantize(TWO_DP, rounding=ROUND_DOWN)
    remainder = total - (base * n)

    splits = []
    for uid in participant_ids:
        amount = base + (remainder if uid == payer_id else Decimal("0.00"))
        splits.append(
            {"user_id": uid, "amount": amount, "percentage": None, "shares": None}
        )

    # Sanity: sum must equal total
    _assert_sum_equals_total(splits, total, "equal")
    return splits


# ─────────────────────────────────────────────────────────────────────────────
# Unequal Split
# ─────────────────────────────────────────────────────────────────────────────

def validate_unequal_splits(total: Decimal, splits_input: list[dict]) -> list[dict]:
    """
    Validate manually-entered amounts and return normalised split data.

    splits_input items: {user_id: int, amount: Decimal}

    Rules:
        - Each individual amount must be ≥ 0.
        - Sum of all amounts must equal the expense total exactly.

    Returns:
        List of dicts: [{user_id, amount, percentage=None, shares=None}]
    """
    if not splits_input:
        raise ExpenseValidationError("At least one split is required.", field="splits")

    splits = []
    running_sum = Decimal("0.00")

    for item in splits_input:
        amount = item["amount"]
        if amount < Decimal("0.00"):
            raise ExpenseValidationError(
                f"Split amount for user {item['user_id']} cannot be negative.",
                field="splits",
            )
        running_sum += amount
        splits.append(
            {"user_id": item["user_id"], "amount": amount, "percentage": None, "shares": None}
        )

    if running_sum != total:
        raise ExpenseValidationError(
            f"Split amounts sum to {running_sum}, but expense total is {total}. "
            "They must be equal.",
            field="splits",
        )

    return splits


# ─────────────────────────────────────────────────────────────────────────────
# Percentage Split
# ─────────────────────────────────────────────────────────────────────────────

def validate_percentage_splits(total: Decimal, splits_input: list[dict]) -> list[dict]:
    """
    Validate percentages and calculate amounts.

    splits_input items: {user_id: int, percentage: Decimal}

    Rules:
        - Each percentage must be ≥ 0.
        - Sum of percentages must be within [99.99, 100.01] to allow rounding.
        - Last participant absorbs any remainder from ROUND_DOWN arithmetic.

    Returns:
        List of dicts: [{user_id, amount, percentage, shares=None}]
    """
    if not splits_input:
        raise ExpenseValidationError("At least one split is required.", field="splits")

    total_pct = Decimal("0.00")
    for item in splits_input:
        pct = item["percentage"]
        if pct < Decimal("0.00"):
            raise ExpenseValidationError(
                f"Percentage for user {item['user_id']} cannot be negative.",
                field="splits",
            )
        total_pct += pct

    lower = Decimal("100.00") - PERCENTAGE_TOLERANCE
    upper = Decimal("100.00") + PERCENTAGE_TOLERANCE
    if not (lower <= total_pct <= upper):
        raise ExpenseValidationError(
            f"Percentages sum to {total_pct}%. They must sum to exactly 100% "
            f"(tolerance ±{PERCENTAGE_TOLERANCE}%).",
            field="splits",
        )

    splits = []
    running_sum = Decimal("0.00")

    for i, item in enumerate(splits_input):
        if i == len(splits_input) - 1:
            amount = total - running_sum
        else:
            amount = (item["percentage"] / Decimal("100") * total).quantize(
                TWO_DP, rounding=ROUND_DOWN
            )
            running_sum += amount

        splits.append(
            {
                "user_id": item["user_id"],
                "amount": amount,
                "percentage": item["percentage"],
                "shares": None,
            }
        )

    _assert_sum_equals_total(splits, total, "percentage")
    return splits


# ─────────────────────────────────────────────────────────────────────────────
# Shares Split
# ─────────────────────────────────────────────────────────────────────────────

def validate_shares_splits(total: Decimal, splits_input: list[dict]) -> list[dict]:
    """
    Validate share counts and calculate proportional amounts.

    splits_input items: {user_id: int, shares: Decimal}

    Rules:
        - Each share count must be ≥ 0.
        - Total shares must be > 0.
        - Participants with 0 shares have amount = 0 (present but owe nothing).
        - Last participant (by position) absorbs remainder.

    Returns:
        List of dicts: [{user_id, amount, percentage=None, shares}]
    """
    if not splits_input:
        raise ExpenseValidationError("At least one split is required.", field="splits")

    for item in splits_input:
        if item["shares"] < Decimal("0.00"):
            raise ExpenseValidationError(
                f"Shares for user {item['user_id']} cannot be negative.",
                field="splits",
            )

    total_shares = sum(item["shares"] for item in splits_input)
    if total_shares <= Decimal("0.00"):
        raise ExpenseValidationError(
            "Total shares must be greater than zero.",
            field="splits",
        )

    splits = []
    running_sum = Decimal("0.00")

    for i, item in enumerate(splits_input):
        if item["shares"] == Decimal("0.00"):
            amount = Decimal("0.00")
        elif i == len(splits_input) - 1:
            amount = total - running_sum
        else:
            amount = (item["shares"] / total_shares * total).quantize(
                TWO_DP, rounding=ROUND_DOWN
            )
            running_sum += amount

        splits.append(
            {
                "user_id": item["user_id"],
                "amount": amount,
                "percentage": None,
                "shares": item["shares"],
            }
        )

    return splits


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _assert_sum_equals_total(splits: list[dict], total: Decimal, split_type: str) -> None:
    """Internal sanity check after calculation. Should never fire in production."""
    calculated_sum = sum(s["amount"] for s in splits)
    if calculated_sum != total:
        raise ExpenseValidationError(
            f"Internal error: {split_type} split calculation produced {calculated_sum} "
            f"but expected {total}. Please report this bug.",
        )
