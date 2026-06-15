"""
Expense serializers.

Serializers are responsible for:
  - Input parsing and field-level validation
  - Calling validators for cross-field rules
  - Structuring read responses

Serializers do NOT call services.
Services are called by views.

Read serializers:
    ExpenseSplitSerializer   — single split row (embedded in expense)
    ExpenseSerializer        — full expense (list + detail responses)

Write serializers:
    SplitInputSerializer     — one split entry in a create/update request
    ExpenseCreateSerializer  — validated input for create_expense()
    ExpenseUpdateSerializer  — validated input for update_expense() (all fields optional)
"""

from decimal import Decimal

from rest_framework import serializers

from apps.expenses.models import Expense, ExpenseSplit
from apps.expenses.validators import ExpenseValidationError
from apps.users.serializers import UserSerializer


# ─────────────────────────────────────────────────────────────────────────────
# Read serializers
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseSplitSerializer(serializers.ModelSerializer):
    """Single split row — embedded inside ExpenseSerializer.splits."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ["id", "user", "amount", "percentage", "shares"]
        read_only_fields = fields


class ExpenseSerializer(serializers.ModelSerializer):
    """Full expense representation for list and detail responses."""

    paid_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)
    split_type_display = serializers.CharField(source="get_split_type_display", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "group",
            "description",
            "amount",
            "category",
            "category_display",
            "expense_date",
            "split_type",
            "split_type_display",
            "paid_by",
            "created_by",
            "splits",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# Write — split input
# ─────────────────────────────────────────────────────────────────────────────

class SplitInputSerializer(serializers.Serializer):
    """
    One entry in the splits list of a create/update request.

    For unequal splits:    provide user_id + amount
    For percentage splits: provide user_id + percentage
    For shares splits:     provide user_id + shares
    For equal splits:      provide user_id only (or use participant_ids field)
    """

    user_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=Decimal("0.00")
    )
    shares = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.00")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Write — create
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseCreateSerializer(serializers.Serializer):
    """
    Input for POST /api/groups/{id}/expenses/

    Split type determines which fields are required inside splits[]:
      equal      → splits[].user_id (no amounts needed)
      unequal    → splits[].user_id + splits[].amount
      percentage → splits[].user_id + splits[].percentage
      shares     → splits[].user_id + splits[].shares

    paid_by defaults to the authenticated user if omitted.
    expense_date defaults to today if omitted.
    """

    description = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    category = serializers.ChoiceField(
        choices=Expense.CATEGORY_CHOICES, default=Expense.CATEGORY_GENERAL
    )
    expense_date = serializers.DateField(required=False)
    split_type = serializers.ChoiceField(choices=Expense.SPLIT_CHOICES, default=Expense.SPLIT_EQUAL)
    paid_by = serializers.IntegerField(min_value=1, required=False)
    splits = SplitInputSerializer(many=True, required=False, default=list)

    def validate_description(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Description cannot be blank.")
        return value

    def validate(self, data: dict) -> dict:
        split_type = data.get("split_type", Expense.SPLIT_EQUAL)
        splits = data.get("splits", [])

        try:
            self._cross_validate_splits(split_type, splits, data.get("amount"))
        except ExpenseValidationError as exc:
            raise serializers.ValidationError({"splits": exc.message})

        return data

    def _cross_validate_splits(self, split_type: str, splits: list, amount) -> None:
        """Validate that the correct fields are present for the chosen split type."""
        if split_type == Expense.SPLIT_EQUAL:
            return  # amounts are calculated — no validation needed here

        if not splits:
            raise ExpenseValidationError(
                f"splits[] is required for split_type='{split_type}'."
            )

        if split_type == Expense.SPLIT_UNEQUAL:
            for s in splits:
                if "amount" not in s or s.get("amount") is None:
                    raise ExpenseValidationError(
                        f"Each split must have 'amount' for split_type='unequal'."
                    )

        elif split_type == Expense.SPLIT_PERCENTAGE:
            for s in splits:
                if "percentage" not in s or s.get("percentage") is None:
                    raise ExpenseValidationError(
                        "Each split must have 'percentage' for split_type='percentage'."
                    )

        elif split_type == Expense.SPLIT_SHARES:
            for s in splits:
                if "shares" not in s or s.get("shares") is None:
                    raise ExpenseValidationError(
                        "Each split must have 'shares' for split_type='shares'."
                    )

    def to_service_args(self, group, created_by) -> dict:
        """
        Convert validated data into keyword arguments for services.create_expense().
        Called by the view after serializer.is_valid().
        """
        from datetime import date as date_type

        data = self.validated_data
        splits = data.get("splits", [])
        split_type = data["split_type"]

        # Derive participant_ids and splits_input from the splits list
        participant_ids = [s["user_id"] for s in splits]
        splits_input = []

        if split_type == Expense.SPLIT_UNEQUAL:
            splits_input = [{"user_id": s["user_id"], "amount": s["amount"]} for s in splits]
        elif split_type == Expense.SPLIT_PERCENTAGE:
            splits_input = [{"user_id": s["user_id"], "percentage": s["percentage"]} for s in splits]
        elif split_type == Expense.SPLIT_SHARES:
            splits_input = [{"user_id": s["user_id"], "shares": s["shares"]} for s in splits]

        return {
            "group": group,
            "created_by": created_by,
            "paid_by_id": data.get("paid_by", created_by.id),
            "description": data["description"],
            "amount": data["amount"],
            "category": data.get("category", Expense.CATEGORY_GENERAL),
            "expense_date": data.get("expense_date", date_type.today()),
            "split_type": split_type,
            "splits_input": splits_input,
            "participant_ids": participant_ids,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Write — update
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseUpdateSerializer(serializers.Serializer):
    """
    Input for PATCH /api/groups/{gid}/expenses/{id}/

    All fields are optional — only provided fields are updated.
    If split_type or amount changes, splits[] must be re-provided.
    """

    description = serializers.CharField(max_length=255, required=False)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    category = serializers.ChoiceField(choices=Expense.CATEGORY_CHOICES, required=False)
    expense_date = serializers.DateField(required=False)
    split_type = serializers.ChoiceField(choices=Expense.SPLIT_CHOICES, required=False)
    paid_by = serializers.IntegerField(min_value=1, required=False)
    splits = SplitInputSerializer(many=True, required=False)

    def validate_description(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Description cannot be blank.")
        return value

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError(
                "Provide at least one field to update."
            )
        return data

    def to_service_args(self, expense: Expense) -> dict:
        """Convert validated data to keyword arguments for services.update_expense()."""
        data = self.validated_data
        splits = data.get("splits")
        split_type = data.get("split_type", expense.split_type)

        participant_ids = None
        splits_input = None

        if splits is not None:
            participant_ids = [s["user_id"] for s in splits]
            if split_type == Expense.SPLIT_UNEQUAL:
                splits_input = [{"user_id": s["user_id"], "amount": s["amount"]} for s in splits]
            elif split_type == Expense.SPLIT_PERCENTAGE:
                splits_input = [{"user_id": s["user_id"], "percentage": s["percentage"]} for s in splits]
            elif split_type == Expense.SPLIT_SHARES:
                splits_input = [{"user_id": s["user_id"], "shares": s["shares"]} for s in splits]
            else:
                splits_input = []

        return {
            "paid_by_id":       data.get("paid_by"),
            "description":      data.get("description"),
            "amount":           data.get("amount"),
            "category":         data.get("category"),
            "expense_date":     data.get("expense_date"),
            "split_type":       data.get("split_type"),
            "splits_input":     splits_input,
            "participant_ids":  participant_ids,
        }
