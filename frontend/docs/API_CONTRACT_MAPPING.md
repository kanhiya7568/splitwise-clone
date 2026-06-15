# API Contract Mapping

Backend base URL: `http://localhost:8000`
All protected endpoints require: `Authorization: Bearer <access_token>`

---

## Authentication

### POST `/api/auth/register/`
**Body**
```json
{ "email": "string", "password": "string", "first_name": "string", "last_name": "string" }
```
**Response 201**
```json
{ "access": "string", "refresh": "string", "user": { "id": 1, "email": "...", "first_name": "...", "last_name": "..." } }
```
**Frontend usage:** `RegisterPage` form submission

---

### POST `/api/auth/login/`
**Body**
```json
{ "email": "string", "password": "string" }
```
**Response 200**
```json
{ "access": "string", "refresh": "string" }
```
**Frontend usage:** `LoginPage` form submission → store tokens → redirect `/`

---

### POST `/api/auth/logout/`
**Body**
```json
{ "refresh": "string" }
```
**Response 205**  No body
**Frontend usage:** Top nav logout button → clear stores → redirect `/login`

---

### POST `/api/auth/token/refresh/`
**Body**
```json
{ "refresh": "string" }
```
**Response 200**
```json
{ "access": "string" }
```
**Frontend usage:** Axios interceptor on 401 → silent refresh → retry original request

---

### GET `/api/auth/me/`
**Response 200**
```json
{ "id": 1, "email": "...", "first_name": "...", "last_name": "..." }
```
**Frontend usage:** App startup hydration → populate `authStore.user`

---

## Groups

### GET `/api/groups/`
**Response 200** `{ count, results: Group[] }`
```json
Group: { "id", "name", "created_by", "created_at", "member_count" }
```
**Frontend usage:** `GroupsPage` list, `DashboardPage` recent groups

---

### POST `/api/groups/`
**Body** `{ "name": "string" }`
**Response 201** `Group`
**Frontend usage:** Create Group Modal

---

### GET `/api/groups/:id/`
**Response 200**
```json
{ "id", "name", "created_by", "members": [Member], "created_at" }
Member: { "id", "user": User, "role": "admin"|"member", "is_active": bool }
```
**Frontend usage:** `GroupDetailPage` header + member list

---

### POST `/api/groups/:id/invite/`
**Body** `{ "email": "string" }`
**Response 200** `{ "message": "..." }`
**Frontend usage:** Invite Members Modal

---

### DELETE `/api/groups/:id/members/:uid/`
**Response 204**
**Frontend usage:** Member list → remove button (admin only)

---

## Expenses

### GET `/api/groups/:gid/expenses/`
**Query params:** `date_from`, `date_to`, `category`, `created_by`, `split_type`
**Response 200** `{ count, results: Expense[] }`
```json
Expense: {
  "id", "description", "amount", "category", "category_display",
  "expense_date", "split_type", "split_type_display",
  "paid_by": User, "created_by": User,
  "splits": [{ "id", "user": User, "amount", "percentage", "shares" }],
  "created_at", "updated_at"
}
```
**Frontend usage:** `GroupDetailPage` expense tab, `DashboardPage` recent expenses

---

### POST `/api/groups/:gid/expenses/`
**Body**
```json
{
  "description": "string",
  "amount": "decimal",
  "category": "food|transport|accommodation|entertainment|utilities|other|general",
  "expense_date": "YYYY-MM-DD",
  "split_type": "equal|unequal|percentage|shares",
  "paid_by": "user_id (optional, defaults to self)",
  "splits": [
    // equal:      [{ "user_id": 1 }, ...]
    // unequal:    [{ "user_id": 1, "amount": "30.00" }, ...]
    // percentage: [{ "user_id": 1, "percentage": "60.00" }, ...]
    // shares:     [{ "user_id": 1, "shares": "2" }, ...]
  ]
}
```
**Response 201** `Expense`
**Frontend usage:** Add Expense Modal

---

### PATCH `/api/groups/:gid/expenses/:eid/edit/`
**Body** Same as POST (all fields optional)
**Response 200** `Expense`
**Frontend usage:** Edit Expense Modal

---

### DELETE `/api/groups/:gid/expenses/:eid/delete/`
**Response 200** `{ "message": "Expense deleted." }`
**Frontend usage:** Expense context menu → delete

---

## Balances

### GET `/api/balances/`
**Response 200** — Global balances for current user
```json
[{ "user1": User, "user2": User, "net_amount": "decimal", "group": { "id", "name" } }]
```
**Frontend usage:** `BalancesPage` global view

---

### GET `/api/groups/:gid/balances/`
**Response 200** — Raw pairwise balances for group
```json
[{ "user1": User, "user2": User, "net_amount": "decimal" }]
```
**Frontend usage:** `GroupDetailPage` balances tab (raw view)

---

### GET `/api/groups/:gid/balances/?view=simplified`
**Response 200** — Minimized settlement transactions
```json
[{ "payer": User, "receiver": User, "amount": "decimal" }]
```
**Frontend usage:** `GroupDetailPage` balances tab (simplified view)

---

## Settlements

### GET `/api/groups/:gid/settlements/`
**Response 200** `{ count, results: Settlement[] }`
```json
Settlement: { "id", "payer": User, "receiver": User, "amount", "note", "created_at", "is_deleted" }
```
**Frontend usage:** `SettlementHistoryPage`

---

### POST `/api/groups/:gid/settlements/`
**Body** `{ "payer_id", "receiver_id", "amount", "note": "" }`
**Response 201** `Settlement`
**Frontend usage:** Record Settlement Modal

---

## Chat

### GET `/api/expenses/:eid/messages/`
**Response 200** `{ count, results: Message[] }`
```json
Message: { "id", "sender": User, "content": "string|[deleted]", "is_deleted": bool, "created_at" }
```
**Frontend usage:** Chat panel initial load

---

### WebSocket `ws://localhost:8000/ws/chat/:eid/?token=<access_token>`

**Client → Server frames:**
```json
{ "type": "chat_message", "content": "string" }
{ "type": "delete_message", "message_id": 123 }
```

**Server → Client frames:**
```json
{ "type": "history", "messages": [Message] }
{ "type": "chat_message", "message": Message }
{ "type": "message_deleted", "message_id": 123 }
{ "type": "error", "message": "..." }
```

**Close codes:**
- `4001` — Unauthenticated → redirect to login
- `4003` — Forbidden (not a member)
- `4004` — Expense not found

---

## Error Response Shape (all endpoints)
```json
{ "error": "string" }          // 400, 403, 404, 500
{ "field_name": ["error"] }    // 400 validation errors
```

## Pagination Shape (all list endpoints)
```json
{ "count": 42, "next": "url|null", "previous": "url|null", "results": [] }
```
