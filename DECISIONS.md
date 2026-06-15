# DECISIONS.md

## Duplicate Handling

Options:

* Auto delete
* User approval

Chosen:
User approval.

Reason:
Avoid accidental data loss.

---

## Currency Conversion

Options:

* Ignore currency
* Convert during import

Chosen:
Convert during import.

Reason:
Trip expenses contained USD values.

---

## Negative Amounts

Options:

* Reject
* Treat as refunds

Chosen:
Refund interpretation.

Reason:
Better representation of real-world scenarios.

---

## Membership Timeline

Options:

* Ignore membership dates
* Enforce timelines

Chosen:
Enforce timelines.

Reason:
Users should not owe expenses outside their active period.

---

## Settlement Rows

Options:

* Treat as expenses
* Convert to settlements

Chosen:
Convert to settlements.

Reason:
Matches business semantics.
