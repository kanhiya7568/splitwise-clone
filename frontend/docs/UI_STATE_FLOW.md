# UI State Flow

---

## 1. Auth Store (Zustand)

```
Store: authStore
─────────────────────────────────────────────
State:
  user: User | null
  accessToken: string | null        ← in-memory only
  isHydrated: boolean               ← true after startup check

Actions:
  login(tokens, user)               ← store access in memory, refresh in localStorage
  logout()                          ← clear memory + localStorage + redirect /login
  setAccessToken(token)             ← called by Axios interceptor after refresh
  hydrate()                         ← called on app mount: check refresh → /api/auth/me/
─────────────────────────────────────────────
```

**Token Storage:**

| Token | Storage | Reason |
|---|---|---|
| `access` | Memory (Zustand) | XSS protection — not in localStorage |
| `refresh` | `localStorage` | Survives page reload |

**Hydration flow on app load:**
```
App mount
  → authStore.hydrate()
    → read refresh from localStorage
    → if exists: POST /api/auth/token/refresh/
      → success: store new access token → GET /api/auth/me/ → store user
      → fail: clear localStorage → user = null → show login
    → if none: user = null
  → set isHydrated = true
  → render app (RequireAuth reads isHydrated + user)
```

---

## 2. UI Store (Zustand)

```
Store: uiStore
─────────────────────────────────────────────
State:
  activeModal: ModalName | null
  modalProps: Record<string, unknown>
  sidebarOpen: boolean              ← mobile drawer

Actions:
  openModal(name, props?)
  closeModal()
  toggleSidebar()
─────────────────────────────────────────────

ModalName enum:
  'create_group'
  'invite_member'
  'add_expense'
  'edit_expense'
  'record_settlement'
  'confirm_delete'
```

**Modal open flow:**
```
User clicks "Add Expense"
  → uiStore.openModal('add_expense', { groupId })
  → AppLayout renders <AddExpenseModal groupId={...} />
  → On success: uiStore.closeModal() + queryClient.invalidateQueries(['expenses', groupId])
  → On cancel: uiStore.closeModal()
```

---

## 3. Chat Store (Zustand)

```
Store: chatStore
─────────────────────────────────────────────
State:
  messages: Record<expenseId, Message[]>
  status: Record<expenseId, 'connecting'|'open'|'closed'|'error'>
  sockets: Record<expenseId, WebSocket>

Actions:
  connect(expenseId, accessToken)
  disconnect(expenseId)
  sendMessage(expenseId, content)
  deleteMessage(expenseId, messageId)
  _onMessage(expenseId, frame)      ← internal: process server frames
─────────────────────────────────────────────
```

**WebSocket lifecycle:**
```
connect(expenseId, token)
  → new WebSocket(`ws://.../ws/chat/${expenseId}/?token=${token}`)
  → onopen:    status[id] = 'open'
  → onmessage: _onMessage(id, JSON.parse(event.data))
  → onerror:   status[id] = 'error' → schedule reconnect (exponential backoff)
  → onclose:
    → code === 4001: authStore.logout()
    → code === 4003: show 403 error toast
    → else:         schedule reconnect

_onMessage(id, frame):
  → frame.type === 'history':        messages[id] = frame.messages
  → frame.type === 'chat_message':   messages[id].push(frame.message)
  → frame.type === 'message_deleted': mark message is_deleted = true
  → frame.type === 'error':          toast.error(frame.message)

disconnect(id):
  → sockets[id].close()
  → delete sockets[id]
  → delete messages[id]
```

---

## 4. TanStack Query — Server State

### Query Keys (canonical)

```typescript
const queryKeys = {
  me:                 () => ['me'],
  groups:             () => ['groups'],
  group:              (id: number) => ['groups', id],
  expenses:           (gid: number) => ['expenses', gid],
  expense:            (gid: number, eid: number) => ['expenses', gid, eid],
  groupBalances:      (gid: number) => ['balances', 'group', gid],
  globalBalances:     () => ['balances', 'global'],
  settlements:        (gid: number) => ['settlements', gid],
  messages:           (eid: number) => ['messages', eid],
}
```

### Cache Invalidation Map

| User action | Mutation | Invalidates |
|---|---|---|
| Create group | POST /api/groups/ | `groups` |
| Invite member | POST /api/groups/:id/invite/ | `group(id)` |
| Remove member | DELETE /api/groups/:id/members/:uid/ | `group(id)` |
| Create expense | POST /api/groups/:gid/expenses/ | `expenses(gid)`, `groupBalances(gid)`, `globalBalances` |
| Edit expense | PATCH …/edit/ | `expenses(gid)`, `expense(gid,eid)`, `groupBalances(gid)`, `globalBalances` |
| Delete expense | DELETE …/delete/ | `expenses(gid)`, `groupBalances(gid)`, `globalBalances` |
| Record settlement | POST /api/groups/:gid/settlements/ | `settlements(gid)`, `groupBalances(gid)`, `globalBalances` |
| Logout | — | all (queryClient.clear()) |

---

## 5. Axios Interceptor — Token Refresh Flow

```
Request interceptor:
  → attach Authorization: Bearer <authStore.accessToken>

Response interceptor (on 401):
  → if refresh token in localStorage:
    → POST /api/auth/token/refresh/
      → success:
        → authStore.setAccessToken(newToken)
        → retry original request with new token
      → fail:
        → authStore.logout()
        → throw error (original request fails)
  → else:
    → authStore.logout()
```

**Only one refresh is in-flight at a time** — subsequent 401s are queued until the first refresh completes.

---

## 6. Expense Form State Machine

```
ExpenseForm internal state:
  splitType: 'equal' | 'unequal' | 'percentage' | 'shares'
  participants: User[]
  splits: SplitEntry[]
  total: Decimal

SplitEntry per splitType:
  equal:      { userId }                         → amounts computed at submit
  unequal:    { userId, amount }                 → sum must === total
  percentage: { userId, percentage }             → sum must === 100
  shares:     { userId, shares }                 → shares > 0, sum > 0

Live preview (computed on every change):
  equal:
    each = floor(total / n)
    remainder = total - each * n → added to payer
  percentage:
    amount = total * (pct / 100) rounded
  shares:
    amount = total * (share / totalShares) rounded

Validation (Zod + React Hook Form):
  → unequal: sum of amounts === total (to 2dp)
  → percentage: sum of percentages === 100 (±0.01 tolerance)
  → shares: all shares >= 0, totalShares > 0
  → payer must be in participants
  → no duplicate participants
  → at least 1 participant
```

---

## 7. Loading States

| Component | Loading state |
|---|---|
| `GroupGrid` | 6× `GroupCard` skeletons |
| `ExpenseList` | 5× `ExpenseRow` skeletons |
| `BalancesTab` | 3× `BalanceRow` skeletons |
| `MessageList` | 8× `MessageBubble` skeletons |
| `DashboardPage` | `StatCard` skeletons |
| `GroupHeader` | Full-width header skeleton |
