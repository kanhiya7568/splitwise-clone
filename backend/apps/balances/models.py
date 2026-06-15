"""
Balance model — cached materialized view of net amounts owed between user pairs.

Design (AI_CONTEXT.md Section 12, AD-05):
  - One row per (group, user_pair) where user1_id < user2_id (enforced by constraint).
  - net_amount > 0 → user2 owes user1 that amount.
  - net_amount < 0 → user1 owes user2 the absolute amount.
  - net_amount = 0 → balanced (row may be retained for audit; service zeroes it out).
  - Updated atomically (SELECT FOR UPDATE) whenever an expense or settlement changes.
  - If corrupted, fully rebuildable from expenses + settlements (see INTERVIEW_PREP.md Q13).
"""

from django.conf import settings
from django.db import models


class Balance(models.Model):
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="balances",
    )
    # user1_id MUST be < user2_id — enforced by CheckConstraint below.
    # This canonical ordering means exactly one row exists per user pair per group.
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="balances_as_user1",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="balances_as_user2",
    )
    # Positive: user2 owes user1. Negative: user1 owes user2.
    # max_digits=12 supports groups with very large cumulative expenses.
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default="0.00",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "balances"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user1", "user2"],
                name="unique_balance_per_group_user_pair",
            ),
            # CRITICAL: ensures exactly one canonical row per pair.
            # Application code must always set user1=min(id), user2=max(id).
            models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F("user2_id")),
                name="balance_user1_id_lt_user2_id",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "user1"], name="balance_group_user1_idx"),
            models.Index(fields=["group", "user2"], name="balance_group_user2_idx"),
        ]

    def __str__(self) -> str:
        return (
            f"Balance[{self.group_id}]: "
            f"user{self.user1_id} ↔ user{self.user2_id} = {self.net_amount}"
        )
