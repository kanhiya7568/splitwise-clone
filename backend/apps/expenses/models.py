"""
Expenses app models: Expense, ExpenseSplit.

Split type determines how the amount is divided across participants.
All monetary values stored as DECIMAL(10,2) — no floating point arithmetic.

Soft-delete: is_deleted=True. Deleting an expense also reverses its
balance impact (handled in Module 7 Balance service).
"""

from django.conf import settings
from django.db import models


class Expense(models.Model):
    # ── Split type choices ────────────────────────────────────────────────────
    SPLIT_EQUAL = "equal"
    SPLIT_UNEQUAL = "unequal"
    SPLIT_PERCENTAGE = "percentage"
    SPLIT_SHARES = "shares"
    SPLIT_CHOICES = [
        (SPLIT_EQUAL, "Equal"),
        (SPLIT_UNEQUAL, "Unequal"),
        (SPLIT_PERCENTAGE, "Percentage"),
        (SPLIT_SHARES, "Shares"),
    ]

    # ── Category choices ──────────────────────────────────────────────────────
    CATEGORY_FOOD = "food"
    CATEGORY_TRANSPORT = "transport"
    CATEGORY_ACCOMMODATION = "accommodation"
    CATEGORY_ENTERTAINMENT = "entertainment"
    CATEGORY_UTILITIES = "utilities"
    CATEGORY_SHOPPING = "shopping"
    CATEGORY_HEALTH = "health"
    CATEGORY_TRAVEL = "travel"
    CATEGORY_GENERAL = "general"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_FOOD, "Food & Drink"),
        (CATEGORY_TRANSPORT, "Transport"),
        (CATEGORY_ACCOMMODATION, "Accommodation"),
        (CATEGORY_ENTERTAINMENT, "Entertainment"),
        (CATEGORY_UTILITIES, "Utilities"),
        (CATEGORY_SHOPPING, "Shopping"),
        (CATEGORY_HEALTH, "Health"),
        (CATEGORY_TRAVEL, "Travel"),
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_OTHER, "Other"),
    ]

    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_paid",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_created",
    )
    description = models.CharField(max_length=255)
    # max_digits=10, decimal_places=2 → max value 99,999,999.99
    # Business rule: 0 < amount <= 999,999.99 enforced via CheckConstraint
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL,
    )
    expense_date = models.DateField()
    split_type = models.CharField(
        max_length=20,
        choices=SPLIT_CHOICES,
        default=SPLIT_EQUAL,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expenses"
        ordering = ["-expense_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0) & models.Q(amount__lte=999999.99),
                name="expense_amount_positive_and_bounded",
            ),
        ]
        indexes = [
            # Primary list query: all active expenses in a group, newest first
            models.Index(
                fields=["group", "is_deleted", "-expense_date"],
                name="expense_group_active_date_idx",
            ),
            # Filter by payer
            models.Index(fields=["paid_by"], name="expense_paid_by_idx"),
            # Filter by category
            models.Index(fields=["group", "category"], name="expense_group_category_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.description} — {self.amount} (Group: {self.group_id})"

    def soft_delete(self) -> None:
        """Mark expense as deleted. Caller must also reverse balance impact."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])


class ExpenseSplit(models.Model):
    """
    One row per participant per expense.

    amount      — always populated; the exact share in currency units
    percentage  — populated only for SPLIT_PERCENTAGE expenses
    shares      — populated only for SPLIT_SHARES expenses

    Constraint: amount >= 0 (participants with 0 shares owe nothing)
    Unique:     (expense, user) — each user has at most one split per expense
    """

    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="splits",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expense_splits",
    )
    # The monetary amount this user owes the payer for this expense
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Only set for percentage splits; null for equal/unequal/shares
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    # Only set for share-based splits; null for equal/unequal/percentage
    shares = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_splits"
        constraints = [
            models.UniqueConstraint(
                fields=["expense", "user"],
                name="unique_split_per_expense_user",
            ),
            models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name="split_amount_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["expense"], name="split_expense_idx"),
            models.Index(fields=["user"], name="split_user_idx"),
        ]

    def __str__(self) -> str:
        return f"Split: {self.user} owes {self.amount} for expense {self.expense_id}"
