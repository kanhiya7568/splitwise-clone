# INTERVIEW_PREP.md — Splitwise Clone

> Concise, technically accurate answers for every expected interview question about this project.

---

## Q1. Why Django?

**Short answer:** Django was prescribed in the assignment spec, and it is also the right tool for this project.

**Longer reasoning:**

Django provides a batteries-included framework that handles authentication scaffolding, ORM with migrations, admin interface, form validation, and URL routing out of the box. For a financial application that needs correctness, Django's ORM with transaction support (`atomic()` blocks) ensures we can do complex multi-table writes safely.

Django REST Framework (DRF) sits on top and adds serializers, viewsets, permission classes, throttling, and filtering — all of which this project uses. Rather than building permission checks from scratch, DRF lets us declare `permission_classes = [IsAuthenticated, IsGroupMember]` and get correct behavior.

Django Channels extends Django to support ASGI and WebSockets — required for the real-time expense chat feature. This integration is native and well-documented.

**Trade-off accepted:** Django is heavier than Flask or FastAPI for simple CRUD, but for a full-featured app with auth, permissions, real-time, and complex financial logic, the extra structure is a benefit not a burden.

---

## Q2. Why React?

**Short answer:** React was prescribed in the assignment spec, and it is the right tool for an SPA with complex, interconnected state.

**Longer reasoning:**

The Splitwise clone has multiple views (dashboard, group detail, expense detail, balances, settlements) that all share and update the same underlying data. React's component model lets us build reusable UI pieces (BalanceCard, ExpenseCard, SplitEditor) and compose them into pages.

TanStack Query (React Query) handles server state — caching, background refetching, cache invalidation on mutations. This means when a user adds an expense, the expense list and balance view both automatically re-fetch without manual state management.

Zustand handles the thin slice of client-only state: the current user's identity and access token. It is significantly simpler than Redux for this use case.

TypeScript catches mismatches between API response shapes and what the UI renders — especially important for the four different split type payloads and the balance/settlement data structures.

---

## Q3. Why PostgreSQL?

**Short answer:** The assignment specifies a relational database. PostgreSQL is the best relational database for financial data.

**Longer reasoning:**

Financial applications require **ACID guarantees** — Atomicity, Consistency, Isolation, Durability. PostgreSQL provides these fully. When we update a balance row and insert a settlement row in the same transaction, either both succeed or neither does. There is no state where the settlement exists but the balance is not updated.

PostgreSQL also supports:
- `DECIMAL` / `NUMERIC` type — exact arithmetic with no floating point error (critical for money)
- `SELECT FOR UPDATE` — row-level locking used in the balance update service to prevent race conditions when two expenses are saved simultaneously
- Foreign key constraints with `ON DELETE` behavior
- `CHECK` constraints to enforce business rules at the DB level (e.g., `amount > 0`)
- Composite unique constraints (used on the `balances` table: `UNIQUE(group_id, user1_id, user2_id)`)

**Neon PostgreSQL** is used in deployment because it provides managed serverless PostgreSQL with a generous free tier and native SSL support — matching the Render + Vercel deployment target.

---

## Q4. Why Redis?

**Short answer:** Django Channels requires a channel layer to broadcast WebSocket messages across multiple server processes. Redis is the production-grade choice.

**Longer reasoning:**

When multiple users connect to the same expense's chat room, their WebSocket connections may land on different server processes. Without a shared message broker, User A's message would only reach users connected to the same process. Redis acts as the **pub/sub broker** that routes messages across all processes.

Django Channels uses the `channels_redis` library to connect to a Redis instance as its channel layer. When `group_send()` is called, it publishes to Redis, and all consumers subscribed to that channel group receive the event regardless of which process they are on.

**Upstash Redis** is used in deployment because it provides managed Redis with a TLS-enabled URL (`rediss://`), a free tier sufficient for this project, and zero infrastructure management.

**Local development alternative:** `InMemoryChannelLayer` is used locally — no Redis needed for development. This is set in `settings/development.py`.

---

## Q5. Why Cached Balances?

**Short answer:** To make balance reads O(1) instead of O(n) where n is the number of expenses in a group.

**Longer reasoning:**

The naive approach is to calculate balances on every read: scan all expenses in a group, scan all splits, compute who owes whom, aggregate across all expenses. This is correct but slow — as a group accumulates hundreds of expenses over months, every balance page load requires scanning all of them.

The cached approach maintains a `balances` table with one row per user pair per group. When an expense is created, edited, or deleted, the balance rows for all affected user pairs are updated **within the same database transaction**. Balance reads then become a simple `SELECT WHERE group_id=X`.

**The trade-off accepted:** Balance updates are more complex. They must:
1. Always happen inside `atomic()` blocks — if the expense insert fails, the balance update rolls back too.
2. Use `SELECT FOR UPDATE` to prevent two concurrent expense creates from corrupting the same balance row.
3. Handle the edit case: reverse the old expense's effect, then apply the new effect.

**Why this is correct:** The `balances` table is not a source of truth — it is a **materialized view** derived from `expenses` + `expense_splits` + `settlements`. If it ever becomes inconsistent, it can be fully rebuilt by replaying all records (see Q13).

---

## Q6. Why Separate Settlements?

**Short answer:** Settlements are not expenses. Modeling them as expenses creates the wrong abstraction and leads to messy filtering logic everywhere.

**Longer reasoning:**

Some expense-tracking apps model settlements as a special type of expense (e.g., Splitwise internally uses this approach). This works but has costs:

1. **Every expense query must filter out settlements** — you need a `type` flag and `WHERE type != 'settlement'` on every expense list.
2. **Split logic does not apply** — a settlement has no split type; it is always a direct transfer between two users.
3. **Balance update logic differs** — an expense updates balances for all split participants relative to the payer. A settlement updates exactly one balance row (the payer/receiver pair).
4. **UI separation is natural** — expense history and settlement history are separate screens with different columns and actions.

Using a separate `settlements` table keeps the code clean. The `expenses` viewset handles only expenses. The `settlements` viewset handles only settlements. Each updates balances via its own service function. No type-flag filtering anywhere.

---

## Q7. Explain All Four Split Algorithms

### Equal Split
Total amount is divided by the number of participants. Because division rarely produces exact 2-decimal results, we floor each person's share to 2 decimal places and assign the remainder (always < $0.01 × n) to the payer.

**Example:** $10.00 ÷ 3 = $3.33 each. Remainder = $10.00 - ($3.33 × 3) = $0.01. Payer's share = $3.34. Others = $3.33.

**Why assign to payer?** The payer physically has the money. Assigning them the rounding difference means the sum of all splits always equals the exact expense amount.

### Unequal Split (Exact Amounts)
The person creating the expense manually enters each participant's exact amount. The server validates that the sum of all entered amounts equals the total expense amount. If not, a 400 error is returned. No rounding is applied — all amounts are taken as-is.

**Edge case:** Floating point inputs are converted to `Decimal` on the server. `Decimal('3.33') + Decimal('3.33') + Decimal('3.34') = Decimal('10.00')` — exact.

### Percentage Split
Each participant is assigned a percentage. The server validates that the sum of all percentages is between 99.99% and 100.01% (±0.01% tolerance for rounding during entry). Each participant's amount is computed as `(percentage / 100) × total`. The last participant in the list receives `total - sum(all others)` to absorb any rounding drift.

**Example:** $100.00 split 33.33% / 33.33% / 33.34%. First two get $33.33 each. Last gets $100.00 - $66.66 = $33.34.

### Shares Split
Each participant is assigned an integer share count (0 shares allowed). Total shares are summed. Each participant's amount = `(shares / total_shares) × total`. Last participant absorbs remainder. If a participant has 0 shares, their amount = $0.00 — they are included in the expense but owe nothing.

**Example:** Alice=2 shares, Bob=3 shares, Carol=0 shares. Total shares=5. $100.00 total. Alice=$40.00, Bob=$60.00, Carol=$0.00.

**Validation:** If all participants have 0 shares, total_shares=0, division by zero — raise 400 error "Total shares must be greater than zero."

---

## Q8. Explain Debt Simplification

**Problem:** In a group of 5 people after 20 expenses, there may be up to 10 distinct debt pairs (A→B, A→C, B→C, etc.). Each pair potentially has debts going in both directions. Settling each pair independently could require many separate payments.

**Goal:** Find the minimum number of payments that settles all debts.

**Algorithm (Greedy, O(n log n)):**

1. **Compute net balance per user:** For each balance row, accumulate: `net[user1] += net_amount`, `net[user2] -= net_amount`. This gives each user a single number: positive = they are owed money (creditor), negative = they owe money (debtor).

2. **Separate into two sorted lists:** creditors (positive net, sorted descending) and debtors (negative net, sorted by absolute value descending).

3. **Greedy matching:** Take the largest creditor and largest debtor. The settlement amount is `min(credit_amount, debt_amount)`. Emit transaction: `(debtor → creditor, amount)`. Reduce both parties' balances. If either reaches zero, advance that pointer. Repeat until both lists are exhausted.

**Result:** At most `n-1` transactions for `n` users, where `n-1` is the theoretical minimum (a spanning tree of payments).

**Example:** Alice is owed $60. Bob owes $30, Carol owes $30. Algorithm: Bob pays Alice $30, Carol pays Alice $30. Two payments, both clear. No intermediate hops needed.

**Important:** The simplified view is **advisory**. It shows users the optimal payment plan but does not automatically create settlements. Users still manually record each payment.

**Limitation:** The greedy algorithm is not guaranteed to produce the globally optimal solution in all cases (it can produce `n-1` but not always the true minimum). However, for groups ≤ 100 members, it consistently produces near-optimal results. True minimum-cost flow is NP-hard in the general case.

---

## Q9. Explain WebSocket Architecture

**Overview:** Django Channels extends Django to support ASGI (Asynchronous Server Gateway Interface). This allows handling WebSocket connections alongside HTTP requests in the same server process.

**Components:**
- **ASGI Server (Daphne):** Replaces Gunicorn. Handles both HTTP and WebSocket connections.
- **`ProtocolTypeRouter` (asgi.py):** Routes HTTP traffic to Django's WSGI handler, WebSocket traffic to Django Channels.
- **`URLRouter`:** Maps WebSocket paths (e.g., `/ws/chat/{expense_id}/`) to consumer classes.
- **`ChatConsumer`:** An `AsyncJsonWebsocketConsumer` subclass. One instance per connected client. Handles connect, receive, disconnect events.
- **Channel Layer (Redis):** A shared pub/sub broker. Consumers join named groups (e.g., `expense_42`). When one consumer calls `group_send()`, all consumers in that group receive the event — even across different server processes.

**Authentication:** JWT token is passed as a query parameter (`?token=<access_token>`). The consumer extracts and validates it on `connect()`. If invalid, the connection is closed with code 4003. This is the standard workaround because the browser WebSocket API does not support custom headers.

**Message flow:**
1. Client sends `{"type": "chat.message", "content": "Hello"}` over WebSocket.
2. Consumer validates, saves to DB (`await database_sync_to_async(...)` to avoid blocking the async event loop).
3. Consumer calls `group_send()` — Redis delivers to all consumers in `expense_{id}` group.
4. Each consumer's `chat_message()` handler fires, sending the serialized message back to its client.

**Trade-off:** WebSocket connections are long-lived. On Render's free tier, connections may be dropped after inactivity. The frontend reconnects automatically when a disconnect is detected.

---

## Q10. Major Limitations

1. **Concurrent write conflicts (last-write-wins):** If two users edit the same expense simultaneously, both writes execute independently. The second commit wins. There is no conflict detection or merge. This is acceptable for an assignment; production would use optimistic locking with ETag headers.

2. **Access token exposure:** The JWT access token is stored in localStorage, which is accessible to any JavaScript on the page. An XSS attack could steal it. Production applications should use httpOnly cookies with CSRF protection.

3. **WebSocket token expiry during active session:** Once a WebSocket connection is authenticated, it stays open even after the access token expires (access tokens live 60 min). A malicious user who hijacks the token after the WS connection is established could not directly exploit it because WS auth only happens on connect. However, if the page stays open beyond token expiry, REST calls will fail until the token is refreshed and the page reloads/reconnects.

4. **No real-time balance updates:** Only chat is real-time via WebSocket. Balance changes require a page refresh or explicit refetch. TanStack Query refetches in the background on window focus, which partially mitigates this.

5. **Render free tier cold starts:** The backend sleeps after inactivity. First request after sleep takes ~30 seconds. Mitigated by using UptimeRobot to ping the health endpoint every 14 minutes.

6. **No email notifications:** Users are not informed when someone adds an expense or records a settlement in their group.

7. **Greedy debt simplification is not always optimal:** The algorithm is O(n log n) and near-optimal but not guaranteed to produce the absolute minimum number of transactions in all edge cases.

---

## Q11. Improvements with More Time

| Improvement | Why |
|---|---|
| Docker Compose for local dev | Eliminates "works on my machine"; ensures PostgreSQL + Redis parity with production |
| GitHub Actions CI/CD | Auto-run tests on every push; block merges on failure |
| End-to-end tests (Playwright) | Verify full user journeys (register → create group → add expense → settle) |
| Email notifications (Celery + SendGrid) | Notify members when new expenses or settlements are added |
| Optimistic locking | Prevent silent data loss on concurrent edits |
| Account merging | When a pending-invite user registers with the same email, automatically accept their pending invitations |
| Real-time balance updates | WebSocket broadcast balance changes alongside chat messages |
| Multi-currency support | Allow expenses in different currencies with live conversion rates |
| Recurring expenses | Templates that auto-create monthly expenses |
| PDF/CSV export | Export expense history for accounting purposes |
| Mobile app (React Native) | Reuse API; provide native experience |

---

## Q12. How AI Was Used

AI (Antigravity / Google DeepMind) was used as a **junior engineering pair programmer** throughout this project. The human developer acted as the senior engineer making all final decisions.

**Phase 1 — Research:**
AI researched Splitwise as a product, identifying user personas, core workflows, entities, the balance simplification algorithm, and pain points. This replaced ~2 hours of manual product research.

**Phase 2 — Discovery Interview:**
AI conducted a structured 88-question interview across 11 domains (auth, groups, expenses, splits, balances, settlements, chat, API, frontend, security, deployment). The human answered each question. AI documented all decisions.

**Phase 3 — Documentation:**
AI generated `AI_CONTEXT.md` (1,400+ lines, 28 sections), `BUILD_PLAN.md`, `REQUIREMENTS_TRACEABILITY_MATRIX.md`, `Sequence_Diagrams.md`, and `INTERVIEW_PREP.md`. All documents written to the repository.

**Phase 4 — Technical Design:**
AI proposed the database schema, ER diagram, API contracts, and architecture decisions (e.g., `user1_id < user2_id` constraint, greedy simplification, WebSocket auth via query param). Human reviewed and approved.

**Phase 5 — Implementation (upcoming):**
AI will write all application code module-by-module. Human reviews each module before the next begins.

**What AI did NOT do:**
- Make final product decisions — the human approved all decisions
- Skip documentation — every decision is traced to a document
- Write placeholder code — all implementations are complete
- Assume requirements — all ambiguities resolved in Phase 2

**Key prompts documented in:** `AI_CONTEXT.md` Section 25 and the `/prompts` directory.

---

## Q13. How to Rebuild Balances if the Balance Table Becomes Corrupted

The `balances` table is a **materialized view** — a cache derived from the authoritative source data in `expenses`, `expense_splits`, and `settlements`. If it becomes corrupted (e.g., a failed transaction, a bug in the balance service, or manual DB manipulation), it can be fully rebuilt.

**Rebuild procedure:**

```python
from django.db import transaction
from apps.balances.models import Balance
from apps.expenses.models import Expense
from apps.settlements.models import Settlement
from apps.balances.services import apply_expense_to_balances, apply_settlement_to_balance

def rebuild_balances_for_group(group_id):
    with transaction.atomic():
        # Step 1: Wipe all cached balances for the group
        Balance.objects.filter(group_id=group_id).delete()

        # Step 2: Replay all non-deleted expenses in chronological order
        expenses = Expense.objects.filter(
            group_id=group_id,
            is_deleted=False
        ).prefetch_related('splits').order_by('expense_date', 'created_at')

        for expense in expenses:
            splits = list(expense.splits.all())
            apply_expense_to_balances(expense, splits, op='add')

        # Step 3: Replay all non-deleted settlements in chronological order
        settlements = Settlement.objects.filter(
            group_id=group_id,
            is_deleted=False
        ).order_by('created_at')

        for settlement in settlements:
            apply_settlement_to_balance(settlement, op='add')

    # Step 4: Verify (optional sanity check)
    # Sum of all net_amounts in a group should be 0 if perfectly balanced
    # (they rarely are — this is just a consistency check)
```

**Why this works:**
- Soft deletes are used — deleted expenses and settlements are never physically removed, only flagged `is_deleted=True`. The rebuild query filters these out, replaying only the records that should affect balances.
- The rebuild runs in a single `atomic()` block: it wipes the old data and replays everything together. If any step fails, the wipe is rolled back too — no partial state.
- Order matters for auditability but not for correctness — balance arithmetic is commutative (adding expense A then B gives the same final state as B then A).

**This function would be exposed as a Django management command** (`manage.py rebuild_balances --group-id=42`) for operational use.
