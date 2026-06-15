"""
Settlement model.

A settlement records a direct payment from payer → receiver that reduces
their outstanding balance. Unlike an expense, a settlement has no splits —
it updates exactly one Balance row (the pair of payer + receiver).

Soft-delete: is_deleted=True. Deleting reverses the balance impact
(handled in Module 8 Settlement service).
"""

from django.conf import settings
from django.db import models


class Settlement(models.Model):
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="settlements",
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="settlements_paid",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="settlements_received",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="settlements_created",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True, default="")
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settlements"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0) & models.Q(amount__lte=999999.99),
                name="settlement_amount_positive_and_bounded",
            ),
            # Cannot settle with yourself.
            models.CheckConstraint(
                check=~models.Q(payer_id=models.F("receiver_id")),
                name="settlement_payer_ne_receiver",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "is_deleted"], name="settlement_group_active_idx"),
            models.Index(fields=["payer"], name="settlement_payer_idx"),
            models.Index(fields=["receiver"], name="settlement_receiver_idx"),
        ]

    def __str__(self) -> str:
        return f"Settlement: {self.payer} → {self.receiver} {self.amount}"

    def soft_delete(self) -> None:
        """Mark settlement as deleted. Caller must also reverse balance impact."""
        self.is_deleted = True
        self.save(update_fields=["is_deleted", "updated_at"])
