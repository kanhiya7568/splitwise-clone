"""
Balance Engine — core service layer.

Canonical ordering: user1_id < user2_id in every Balance row.

net_amount semantics:
    > 0  →  user2 owes user1
    < 0  →  user1 owes user2
    = 0  →  balanced (row deleted to keep table clean)

All public functions must be called inside an existing transaction.atomic()
(e.g. from expenses/services.py or settlements/services.py).
The internal _update_balance helper also wraps itself in select_for_update
to prevent lost-update race conditions under concurrent requests.

Balance delta formula (works for both expense and settlement callers):
    delta = amount * sign  if creditor_id == user1_id
    delta = -(amount * sign) otherwise

Where:
    sign = +1  → add debt   (apply expense / reverse settlement)
    sign = -1  → remove debt (reverse expense / apply settlement)
"""

from decimal import Decimal

from django.db import transaction

from apps.balances.models import Balance
from apps.expenses.models import Expense, ExpenseSplit
from apps.groups.models import Group

_ZERO = Decimal("0.00")


# ─────────────────────────────────────────────────────────────────────────────
# Core helper
# ─────────────────────────────────────────────────────────────────────────────

def _update_balance(
    group: Group,
    creditor_id: int,
    debtor_id: int,
    amount: Decimal,
    sign: int,
) -> None:
    """
    Apply a signed delta to one Balance row.

    creditor_id: user who is owed money (expense payer, settlement receiver)
    debtor_id:   user who owes money    (expense participant, settlement payer)
    amount:      absolute amount of the transfer
    sign:        +1 to increase debt, -1 to decrease debt

    Creates the Balance row if it does not exist.
    Deletes the Balance row if net_amount reaches exactly zero.
    Uses SELECT FOR UPDATE to prevent concurrent lost-updates.
    """
    if creditor_id == debtor_id:
        return  # payer's own split — no balance change

    u1_id = min(creditor_id, debtor_id)
    u2_id = max(creditor_id, debtor_id)

    # Signed delta from the perspective of "how much does user2 owe user1"
    delta = (amount * sign) if creditor_id == u1_id else -(amount * sign)

    with transaction.atomic():
        # get_or_create then select_for_update is safe inside an outer atomic block
        balance, _ = Balance.objects.get_or_create(
            group=group,
            user1_id=u1_id,
            user2_id=u2_id,
            defaults={"net_amount": _ZERO},
        )
        # Re-fetch with a row-level lock before mutating
        balance = Balance.objects.select_for_update().get(pk=balance.pk)
        balance.net_amount += delta

        if balance.net_amount == _ZERO:
            balance.delete()
        else:
            balance.save(update_fields=["net_amount", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# Expense → Balance
# ─────────────────────────────────────────────────────────────────────────────

def apply_expense_to_balances(
    expense: Expense,
    splits: list[ExpenseSplit],
) -> None:
    """
    Increase balances to reflect a newly created (or re-applied) expense.

    For every split where participant != payer:
        debtor owes payer split.amount more.

    The payer's own split is skipped — a person does not owe themselves.

    Args:
        expense: The Expense that was created.
        splits:  Its ExpenseSplit rows (already saved to DB).
    """
    payer_id = expense.paid_by_id
    for split in splits:
        if split.user_id == payer_id:
            continue
        _update_balance(
            group=expense.group,
            creditor_id=payer_id,
            debtor_id=split.user_id,
            amount=split.amount,
            sign=1,
        )


def reverse_expense_from_balances(
    expense: Expense,
    splits: list[ExpenseSplit],
) -> None:
    """
    Undo the balance impact of an expense (called before edit or delete).

    Mirrors apply_expense_to_balances with sign=-1.

    Args:
        expense: The Expense being reversed.
        splits:  The splits whose amounts should be reversed.
                 Pass the OLD splits before they are deleted or overwritten.
    """
    payer_id = expense.paid_by_id
    for split in splits:
        if split.user_id == payer_id:
            continue
        _update_balance(
            group=expense.group,
            creditor_id=payer_id,
            debtor_id=split.user_id,
            amount=split.amount,
            sign=-1,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Settlement → Balance
# ─────────────────────────────────────────────────────────────────────────────

def apply_settlement_to_balances(settlement) -> None:
    """
    Reduce balances to reflect a settlement payment.

    settlement.payer    = the debtor making the payment
    settlement.receiver = the creditor receiving the payment

    A settlement reduces debt, so sign=-1 (creditor perspective).

    Args:
        settlement: A saved Settlement instance.
    """
    _update_balance(
        group=settlement.group,
        creditor_id=settlement.receiver_id,
        debtor_id=settlement.payer_id,
        amount=settlement.amount,
        sign=-1,
    )


def reverse_settlement_from_balances(settlement) -> None:
    """
    Undo the balance impact of a settlement (called before settlement delete).

    Mirrors apply_settlement_to_balances with sign=+1.

    Args:
        settlement: The Settlement being reversed.
    """
    _update_balance(
        group=settlement.group,
        creditor_id=settlement.receiver_id,
        debtor_id=settlement.payer_id,
        amount=settlement.amount,
        sign=1,
    )
