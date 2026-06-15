"""
Debt simplification — greedy algorithm.

Goal: Given each user's net balance in a group, produce the minimum
number of settlement transactions needed to fully settle all debts.

Net balance semantics (input):
    positive → user is owed money (creditor)
    negative → user owes money (debtor)
    zero     → already settled (excluded from algorithm)

Algorithm (greedy):
    1. Separate users into creditors and debtors.
    2. Sort both lists: largest absolute amount first.
       Tiebreaker: smallest user_id first (deterministic ordering).
    3. While creditors and debtors both non-empty:
       a. Pick the largest creditor C (owed C_amt).
       b. Pick the largest debtor D (owes D_amt).
       c. settle = min(C_amt, D_amt)
       d. Record transaction: D pays C settle
       e. C_amt -= settle; D_amt -= settle
       f. Remove whichever reached zero; re-sort.
    4. Return list of transactions.

Complexity: O(N² log N) worst case — acceptable for groups (N typically < 50).

Bound: at most N−1 transactions where N = number of non-zero-balance users.
Each transaction zeroes out at least one party, so at most N−1 steps remain.

DB helper:
    compute_net_balances_for_group(group)
        Aggregates the pairwise Balance rows into per-user net positions.
        Signs: position[user1] += net_amount, position[user2] -= net_amount
"""

from decimal import Decimal

_ZERO = Decimal("0.00")


# ─────────────────────────────────────────────────────────────────────────────
# Pure simplification (no DB access)
# ─────────────────────────────────────────────────────────────────────────────

def simplify_debts(net_balances: list[dict]) -> list[dict]:
    """
    Compute the minimum set of transactions to settle a list of net balances.

    Args:
        net_balances: [{'user_id': int, 'amount': Decimal}, ...]
            amount > 0  → user is a creditor (owed money)
            amount < 0  → user is a debtor   (owes money)
            amount == 0 → ignored

    Returns:
        [{'payer_id': int, 'receiver_id': int, 'amount': Decimal}, ...]
        Ordered by: amount descending, payer_id ascending, receiver_id ascending.
        Empty list if all balances are zero.

    Raises:
        ValueError: If the net balances do not sum to zero (corrupted data).
    """
    # ── Validate: credits must equal debts ───────────────────────────────────
    total = sum(entry["amount"] for entry in net_balances)
    if total != _ZERO:
        raise ValueError(
            f"Net balances do not sum to zero (sum={total}). "
            "Balance data may be corrupted. "
            "Run the balance rebuild procedure to correct."
        )

    # ── Separate into creditors / debtors ────────────────────────────────────
    # Each entry: [abs_amount, user_id]
    creditors: list[list] = []
    debtors: list[list] = []

    for entry in net_balances:
        amt = entry["amount"]
        uid = entry["user_id"]
        if amt > _ZERO:
            creditors.append([amt, uid])
        elif amt < _ZERO:
            debtors.append([-amt, uid])   # store positive magnitude

    transactions: list[dict] = []

    # ── Greedy loop ──────────────────────────────────────────────────────────
    while creditors and debtors:
        # Sort: largest amount first, smallest user_id as tiebreaker
        creditors.sort(key=lambda x: (-x[0], x[1]))
        debtors.sort(key=lambda x: (-x[0], x[1]))

        cred_amt, cred_uid = creditors[0]
        debt_amt, debt_uid = debtors[0]

        settle = min(cred_amt, debt_amt)

        transactions.append(
            {
                "payer_id": debt_uid,
                "receiver_id": cred_uid,
                "amount": settle,
            }
        )

        creditors[0][0] -= settle
        debtors[0][0] -= settle

        if creditors[0][0] == _ZERO:
            creditors.pop(0)
        if debtors[0][0] == _ZERO:
            debtors.pop(0)

    # ── Deterministic output ordering ─────────────────────────────────────────
    # Sort by amount descending, then payer_id, then receiver_id
    transactions.sort(key=lambda t: (-t["amount"], t["payer_id"], t["receiver_id"]))

    return transactions


# ─────────────────────────────────────────────────────────────────────────────
# DB helper
# ─────────────────────────────────────────────────────────────────────────────

def compute_net_balances_for_group(group) -> list[dict]:
    """
    Aggregate pairwise Balance rows into per-user net positions.

    Balance row semantics:
        net_amount > 0 → user2 owes user1
        net_amount < 0 → user1 owes user2

    Therefore:
        position[user1] += net_amount
        position[user2] -= net_amount

    Args:
        group: A Group instance.

    Returns:
        [{'user_id': int, 'amount': Decimal}, ...]
        Only non-zero positions are returned.
    """
    from apps.balances.models import Balance

    net: dict[int, Decimal] = {}

    for b in Balance.objects.filter(group=group):
        net[b.user1_id] = net.get(b.user1_id, _ZERO) + b.net_amount
        net[b.user2_id] = net.get(b.user2_id, _ZERO) - b.net_amount

    return [
        {"user_id": uid, "amount": amt}
        for uid, amt in sorted(net.items())  # sorted for determinism
        if amt != _ZERO
    ]


def get_simplified_debts_for_group(group) -> list[dict]:
    """
    Full pipeline: fetch DB balances → compute net positions → simplify.

    Args:
        group: A Group instance.

    Returns:
        Minimal list of settlement transactions.
        See simplify_debts() for output format.
    """
    net_balances = compute_net_balances_for_group(group)
    if not net_balances:
        return []
    return simplify_debts(net_balances)
