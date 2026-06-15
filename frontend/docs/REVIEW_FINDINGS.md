# REVIEW_FINDINGS.md
## Phase 6A Design Review — Senior Frontend Architect

Cross-referenced against actual backend source files.

---

## Summary Table

| ID | Severity | Area | One-Line Summary |
|---|---|---|---|
| CRITICAL-01 | 🔴 Critical | Backend | Balance views/routes do not exist in backend |
| CRITICAL-02 | 🔴 Critical | State | Balance net_amount user-perspective logic undefined |
| CRITICAL-03 | 🔴 Critical | API Contract | Settlement edit/delete/detail endpoints missing from mapping |
| CRITICAL-04 | 🔴 Critical | API Contract | Group rename/delete/members endpoints missing from mapping |
| CRITICAL-05 | 🔴 Critical | WebSocket | Reconnect re-uses stale (expired) access token |
| MAJOR-01 | 🟠 Major | State | WebSocket instances non-serializable stored in Zustand |
| MAJOR-02 | 🟠 Major | Components | 6 components missing from FOLDER_STRUCTURE.md |
| MAJOR-03 | 🟠 Major | State | 5 cache invalidation entries missing |
| MAJOR-04 | 🟠 Major | Forms | ExpenseForm must use useFieldArray not manual state |
| MAJOR-05 | 🟠 Major | Responsive | ExpenseDetailPage mobile 2-col layout undefined |
| MAJOR-06 | 🟠 Major | Reliability | No ErrorBoundary components planned anywhere |
| MAJOR-07 | 🟠 Major | UX | SettlementHistoryPage redundant with SettlementsTab |
| MAJOR-08 | 🟠 Major | UX | Empty states for chat/balances not defined |
| MINOR-01 | 🟡 Minor | TypeScript | Strict mode not specified in build plan |
| MINOR-02 | 🟡 Minor | WebSocket | Max retry count and max delay undefined |
| MINOR-03 | 🟡 Minor | API | api/ return type convention undocumented |
| MINOR-04 | 🟡 Minor | Deploy | CORS production origin configuration undocumented |
| MINOR-05 | 🟡 Minor | Performance | No scroll anchoring plan for large message list |
| MINOR-06 | 🟡 Minor | Reliability | ChatPanel needs its own isolated ErrorBoundary |
| MINOR-07 | 🟡 Minor | UX | No user profile/settings page or route |
| MINOR-08 | 🟡 Minor | Polish | Sonner position and theme not specified |
| MINOR-09 | 🟡 Minor | DX | Suspense boundaries not leveraged (React 19 feature) |

---

## CRITICAL Findings

### CRITICAL-01 — Balance Views Do Not Exist

**Affected docs:** API_CONTRACT_MAPPING.md, FOLDER_STRUCTURE.md

**Finding:**
`apps/balances/urls.py` currently contains:
```python
urlpatterns = []  # populated in Module 7
```
There are no balance views, no serializers, and no URL routes in the backend.
Every balance endpoint listed in API_CONTRACT_MAPPING.md will return 404.

**Impact:** Dashboard BalanceSummaryBar, BalancesPage, and GroupDetailPage BalancesTab
are all broken at runtime. This affects 3 of 7 protected pages.

**Recommended Fix:**
Before Phase 6B: implement the missing backend module —
apps/balances/views.py, apps/balances/serializers.py, apps/balances/urls.py.
This is a backend task, not a frontend task, but it blocks frontend implementation.

---

### CRITICAL-02 — Balance net_amount User-Perspective Interpretation Undefined

**Affected docs:** UI_STATE_FLOW.md, COMPONENT_TREE.md

**Finding:**
The backend uses canonical ordering (user1_id < user2_id) with a signed net_amount:
- net_amount > 0 means user2 owes user1
- net_amount < 0 means user1 owes user2

No document describes how the frontend converts this into "you owe X" / "X owes you".
The BalanceRow component is listed but its interpretation logic is undefined.

**Example:** User A (id=1), User B (id=5), net_amount = 30.00
- Means: B owes A $30
- Logged-in as A: show "B owes you $30" 
- Logged-in as B: show "You owe A $30"
- Without this logic the frontend shows a meaningless signed decimal.

**Recommended Fix:**
Add resolveBalance(balance, currentUserId) utility to lib/utils.ts.
Document the algorithm in UI_STATE_FLOW.md. Apply in BalanceRow and SimplifiedRow.

---

### CRITICAL-03 — Settlement Edit/Delete/Detail APIs Missing From Mapping

**Affected docs:** API_CONTRACT_MAPPING.md

**Finding:**
Backend exposes (verified in apps/settlements/urls.py):
- GET  /api/groups/{gid}/settlements/{sid}/
- PATCH /api/groups/{gid}/settlements/{sid}/edit/
- DELETE /api/groups/{gid}/settlements/{sid}/delete/

None appear in API_CONTRACT_MAPPING.md. SettlementRow has no edit or delete actions.
Cache invalidation for settlement mutations is also missing.

**Recommended Fix:**
Add all 3 endpoints to API_CONTRACT_MAPPING.md.
Add Edit/Delete actions to SettlementRow (participant-only).
Add invalidation: settlements(gid) + groupBalances(gid) + globalBalances on both.

---

### CRITICAL-04 — Group Rename/Delete/Members Endpoints Missing From Mapping

**Affected docs:** API_CONTRACT_MAPPING.md

**Finding:**
Backend exposes (verified in apps/groups/urls.py):
- PATCH  /api/groups/{id}/update/   (rename, admin only)
- DELETE /api/groups/{id}/delete/   (soft-delete, admin only)
- GET    /api/groups/{id}/members/  (member list — SEPARATE from group detail)

None appear in API_CONTRACT_MAPPING.md.
The mapping shows DELETE /api/groups/{id}/members/{uid}/ but lists member fetch
inside GET /api/groups/{id}/ which is incorrect — members are at a separate URL.

**Recommended Fix:**
Correct API_CONTRACT_MAPPING.md for all 3 endpoints.
Add group rename action to GroupHeader component (admin only, with inline edit UX).
Add group delete to GroupHeader (admin only, with confirmation dialog).

---

### CRITICAL-05 — WebSocket Reconnect Will Use Expired Access Token

**Affected docs:** UI_STATE_FLOW.md

**Finding:**
chatStore.connect() builds the WebSocket URL with the current access token.
On reconnect after disconnect, if the access token has expired (typically 5-15 min),
the backend will reject with close code 4001, triggering authStore.logout() incorrectly.
The current plan has no mechanism to refresh the token before a reconnect attempt.

**Recommended Fix:**
In the reconnect handler, always read the CURRENT token from authStore.getState().accessToken.
If that token is expired or absent, call the refresh endpoint first.
Only after a valid token is confirmed, open a new WebSocket connection.
Distinguish 4001-on-reconnect from 4001-on-initial-connect to avoid premature logout.

---

## MAJOR Findings

### MAJOR-01 — WebSocket Instances Must Not Live in Zustand State

**Affected docs:** UI_STATE_FLOW.md

**Finding:**
chatStore defines sockets: Record<expenseId, WebSocket> as Zustand state.
WebSocket objects are non-serializable and will break React DevTools,
trigger unintended re-renders, and violate Zustand's design contract.

**Recommended Fix:**
Store WebSocket instances in a module-level Map outside Zustand:
```
const socketRegistry = new Map<number, WebSocket>()
```
Zustand only stores serializable state: messages, status strings, and reconnect counters.

---

### MAJOR-02 — Six Components Missing From FOLDER_STRUCTURE.md

**Affected docs:** COMPONENT_TREE.md vs FOLDER_STRUCTURE.md

**Finding:**
Components in COMPONENT_TREE.md with no file in FOLDER_STRUCTURE.md:

| Component | Used In | Correct Location |
|---|---|---|
| CategoryIcon | ExpenseRow | components/expense/ |
| SplitBadge | ExpenseRow | components/expense/ |
| StatCard | DashboardPage | components/ui/ |
| UserMenu | Sidebar | components/layout/ |
| GroupGrid | GroupsPage | components/group/ |
| GroupHeader | GroupDetailPage | components/group/ |

**Recommended Fix:**
Add all 6 to FOLDER_STRUCTURE.md in the correct directories.

---

### MAJOR-03 — Cache Invalidation Gaps

**Affected docs:** UI_STATE_FLOW.md

**Finding:**
Missing entries from the cache invalidation map:

| Mutation | Missing Invalidations |
|---|---|
| Group rename (PATCH) | groups, group(id) |
| Group delete (DELETE) | groups, group(id) |
| Remove member (DELETE) | groupBalances(gid) |
| Settlement edit (PATCH) | settlements(gid), groupBalances(gid), globalBalances |
| Settlement delete (DELETE) | settlements(gid), groupBalances(gid), globalBalances |

**Recommended Fix:** Add all 5 rows to the invalidation table in UI_STATE_FLOW.md.

---

### MAJOR-04 — ExpenseForm Must Use useFieldArray

**Affected docs:** UI_STATE_FLOW.md

**Finding:**
The ExpenseForm state machine manages splits: SplitEntry[] as plain React state
alongside React Hook Form. This causes dirty-state mismatches, broken reset(),
and uncontrolled/controlled conflicts — a well-known interview red flag.

**Recommended Fix:**
Define splits as a useFieldArray within the RHF useForm context.
Use Zod z.array(splitEntrySchema) with .superRefine() for cross-field validation.

---

### MAJOR-05 — ExpenseDetailPage Mobile Layout Undefined

**Affected docs:** COMPONENT_TREE.md

**Finding:**
ExpenseDetailPage renders ExpenseHeader + SplitBreakdown + ChatPanel
in an implicit 2-column desktop layout. On mobile (< 640px) this is unusable.
No breakpoint behavior is specified.

**Recommended Fix:**
Define a tab-based mobile layout:
- Tab 1: "Details" — ExpenseHeader + SplitBreakdown
- Tab 2: "Chat" — ChatPanel

This mirrors the Splitwise mobile app pattern.

---

### MAJOR-06 — No ErrorBoundary Components

**Affected docs:** FRONTEND_BUILD_PLAN.md, FOLDER_STRUCTURE.md

**Finding:**
No ErrorBoundary is mentioned anywhere. React 19 requires class-based error boundaries
for render errors. With TanStack Query, WebSocket, and async data, crashes will occur.
An unhandled render error without an ErrorBoundary crashes the entire app tree.

**Recommended Fix:**
Add components/ui/ErrorBoundary.tsx and components/ui/ErrorFallback.tsx.
Wrap each page route in AppLayout with an ErrorBoundary.
Add a ChatPanel-specific ErrorBoundary (MINOR-06).

---

### MAJOR-07 — SettlementHistoryPage Is Redundant

**Affected docs:** FRONTEND_ROUTE_MAP.md, COMPONENT_TREE.md

**Finding:**
GroupDetailPage already has a SettlementsTab. The separate /groups/:groupId/settlements
route duplicates the same data. This is confusing UX and double maintenance burden.

**Recommended Fix (Recommended):**
Remove SettlementHistoryPage as a separate route.
Enhance SettlementsTab with full pagination and the Record Settlement modal inline.

---

### MAJOR-08 — Empty States for Chat and Balances Not Defined

**Affected docs:** UI_STATE_FLOW.md

**Finding:**
The loading state table covers skeletons but no empty states are defined for:
- Chat with zero messages (what prompt/CTA is shown?)
- Balances with zero debts (Splitwise's "All settled up!" moment — high interview visibility)
- Simplified balances that reduce to zero transactions

**Recommended Fix:**
Add empty state specifications for all 3 cases.
The zero-balance state should show a green checkmark with "All settled up!"
This is the most recognisable Splitwise UX moment.

---

## MINOR Findings

### MINOR-01 — TypeScript Strict Mode Not Specified
Add "strict": true, "noUncheckedIndexedAccess": true to tsconfig.app.json.

### MINOR-02 — WebSocket Max Retry Undefined
Define: 1s initial, 2x multiplier, 30s max delay, 10 max attempts. After 10: show manual reconnect button.

### MINOR-03 — api/ Return Type Convention Undocumented
Standardise: all api/ functions return T (data directly), not AxiosResponse<T>.

### MINOR-04 — CORS Production Origin Undocumented
Add to deployment checklist: add frontend origin to backend CORS_ALLOWED_ORIGINS.

### MINOR-05 — Large Message List Performance
For MessageList with thousands of messages, use scroll-anchoring to the bottom.
Consider react-virtual if message count is uncapped per expense.

### MINOR-06 — ChatPanel Needs Isolated ErrorBoundary
A crash inside ChatPanel must not crash ExpenseDetailPage.
Wrap ChatPanel in its own ErrorBoundary with a reconnect fallback.

### MINOR-07 — No User Profile Page
Add a read-only /profile route showing current user info from GET /api/auth/me/.

### MINOR-08 — Sonner Position Not Specified
Define: <Toaster position="bottom-right" richColors /> in App.tsx.

### MINOR-09 — Suspense Boundaries Not Leveraged
React 19 + TanStack Query v5 supports useSuspenseQuery + <Suspense>.
Adopting this pattern signals React 19 awareness in interview context.
