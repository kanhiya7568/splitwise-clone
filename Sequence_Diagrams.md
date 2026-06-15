# Sequence Diagrams — Splitwise Clone

> All diagrams rendered in Mermaid. These represent the exact server-side and client-side flows for the four critical operations in the system.

---

## SD-01 — Add Expense

```mermaid
sequenceDiagram
    autonumber
    actor U as User (Browser)
    participant FE as React Frontend
    participant AX as Axios Client
    participant DRF as Django REST API
    participant SVC as Split Service
    participant BAL as Balance Service
    participant DB as PostgreSQL (Neon)

    U->>FE: Fills expense form (amount, split type, participants)
    FE->>FE: Client-side validation (amount > 0, participants selected)
    FE->>AX: POST /api/groups/{gid}/expenses/ {description, amount, category, expense_date, paid_by, split_type, splits[]}
    AX->>AX: Attach Authorization: Bearer <access_token>
    AX->>DRF: HTTP POST

    DRF->>DRF: Authenticate JWT token
    DRF->>DB: SELECT group WHERE id={gid} AND is_deleted=False
    DRF->>DB: SELECT group_membership WHERE group_id={gid} AND user_id={me} AND is_active=True
    alt Not a member
        DRF-->>AX: 403 Forbidden
        AX-->>FE: Error
        FE-->>U: "You are not a member of this group"
    end

    DRF->>DRF: Validate expense fields (amount range, category enum, date present)
    DRF->>DB: SELECT group_membership WHERE group_id={gid} AND user_id IN (split_user_ids) AND is_active=True
    alt Any participant is not active member
        DRF-->>AX: 400 Bad Request "Participant X is not an active member"
        AX-->>FE: Validation error
    end

    DRF->>SVC: calculate_splits(split_type, amount, split_data, payer_id)
    SVC->>SVC: Apply split algorithm (equal/unequal/percentage/shares)
    alt Split validation fails (amounts don't sum, pct != 100, zero total shares)
        SVC-->>DRF: raises ValidationError
        DRF-->>AX: 400 Bad Request {details}
    end
    SVC-->>DRF: List of validated ExpenseSplit objects

    DRF->>DB: BEGIN TRANSACTION (atomic)
    DRF->>DB: INSERT INTO expenses (group_id, paid_by_id, created_by_id, description, amount, category, expense_date, split_type)
    DRF->>DB: INSERT INTO expense_splits (expense_id, user_id, amount, percentage, shares) × N rows

    DRF->>BAL: apply_expense_to_balances(expense, splits, op='add')
    loop For each split where split.user_id != payer_id
        BAL->>BAL: Compute (user1_id, user2_id) where user1_id < user2_id
        BAL->>BAL: Compute delta (+ or - based on who is creditor)
        BAL->>DB: SELECT FOR UPDATE FROM balances WHERE group_id=X AND user1_id=A AND user2_id=B
        alt Row exists
            BAL->>DB: UPDATE balances SET net_amount = net_amount + delta, updated_at = NOW()
        else Row does not exist
            BAL->>DB: INSERT INTO balances (group_id, user1_id, user2_id, net_amount=delta)
        end
    end

    DB-->>DRF: All writes committed
    DRF->>DB: COMMIT TRANSACTION

    DRF-->>AX: 201 Created {expense with splits, group, paid_by, created_by}
    AX-->>FE: Response data
    FE->>FE: Invalidate React Query cache (expenses list, balances)
    FE-->>U: Expense appears in list; balances update on screen
```

---

## SD-02 — Settle Debt

```mermaid
sequenceDiagram
    autonumber
    actor U as User (Browser)
    participant FE as React Frontend
    participant AX as Axios Client
    participant DRF as Django REST API
    participant BAL as Balance Service
    participant DB as PostgreSQL (Neon)

    U->>FE: Clicks "Settle Up", fills settlement form (payer, receiver, amount, optional note)
    FE->>FE: Client-side validation (payer != receiver, amount > 0)
    FE->>AX: POST /api/groups/{gid}/settlements/ {payer_id, receiver_id, amount, note}
    AX->>AX: Attach Authorization: Bearer <access_token>
    AX->>DRF: HTTP POST

    DRF->>DRF: Authenticate JWT token
    DRF->>DB: Check requester is active member of group
    DRF->>DRF: Validate payer_id != receiver_id
    DRF->>DRF: Validate amount > 0 AND amount <= 999999.99

    DRF->>DB: SELECT group_membership WHERE user_id IN (payer_id, receiver_id) AND group_id={gid} AND is_active=True
    alt Either party is not an active member
        DRF-->>AX: 400 Bad Request "Payer or receiver is not an active member"
        AX-->>FE: Error displayed
    end

    DRF->>DB: BEGIN TRANSACTION (atomic)
    DRF->>DB: INSERT INTO settlements (group_id, payer_id, receiver_id, created_by_id, amount, note)

    DRF->>BAL: apply_settlement_to_balance(settlement, op='add')
    BAL->>BAL: Determine user1 (lower id), user2 (higher id) between payer and receiver
    alt payer.id < receiver.id
        BAL->>BAL: delta = +amount (net_amount moves toward 0; payer owes receiver less)
    else payer.id > receiver.id
        BAL->>BAL: delta = -amount (net_amount moves toward 0; receiver is owed less)
    end
    BAL->>DB: SELECT FOR UPDATE FROM balances WHERE group_id=X AND user1_id=A AND user2_id=B
    alt Row exists
        BAL->>DB: UPDATE balances SET net_amount = net_amount + delta
    else No existing balance row (first interaction)
        BAL->>DB: INSERT INTO balances (group_id, user1_id, user2_id, net_amount=delta)
    end

    DB-->>DRF: Writes committed
    DRF->>DB: COMMIT TRANSACTION

    DRF-->>AX: 201 Created {settlement object}
    AX-->>FE: Response
    FE->>FE: Invalidate React Query cache (settlements list, balances)
    FE-->>U: Settlement appears in history; balance updated on screen

    Note over BAL,DB: If net_amount crosses zero after update,<br/>balance now shows receiver owes payer the difference.<br/>No special handling needed — sign encodes direction.
```

---

## SD-03 — Expense Chat (WebSocket)

```mermaid
sequenceDiagram
    autonumber
    actor U1 as User 1 (Sender)
    actor U2 as User 2 (Viewer)
    participant WS1 as Browser WS (U1)
    participant WS2 as Browser WS (U2)
    participant CON as ChatConsumer (Django Channels)
    participant RL as Redis Channel Layer (Upstash)
    participant DB as PostgreSQL (Neon)

    Note over U1,DB: === CONNECTION PHASE ===

    U1->>WS1: Open ExpenseDetailPage
    WS1->>CON: ws://host/ws/chat/{expense_id}/?token=<access_token>
    CON->>CON: Extract token from query string
    CON->>CON: AccessToken(token) — validate via simplejwt
    alt Token invalid or expired
        CON-->>WS1: Close(code=4003, reason="Unauthorized")
    end
    CON->>DB: SELECT expense WHERE id={expense_id}
    CON->>DB: SELECT group_membership WHERE group_id=expense.group_id AND user_id=token.user_id AND is_active=True
    alt User not a member of the expense's group
        CON-->>WS1: Close(code=4003, reason="Not a member")
    end
    CON->>RL: group_add("expense_{expense_id}", channel_name_1)
    CON-->>WS1: accept() — connection open

    U2->>WS2: Open same ExpenseDetailPage
    WS2->>CON: ws://host/ws/chat/{expense_id}/?token=<access_token_2>
    CON->>CON: Validate token for User 2
    CON->>RL: group_add("expense_{expense_id}", channel_name_2)
    CON-->>WS2: accept() — connection open

    Note over U1,DB: === INITIAL HISTORY LOAD (REST, not WebSocket) ===

    WS1->>DB: GET /api/expenses/{expense_id}/messages/?page_size=50
    DB-->>WS1: Latest 50 messages (sorted by created_at DESC, returned ASC)
    WS1-->>U1: Render chat history

    Note over U1,DB: === SEND MESSAGE PHASE ===

    U1->>WS1: Types "Hello everyone!" and hits Send
    WS1->>CON: {"type": "chat.message", "content": "Hello everyone!"}
    CON->>CON: Validate content: non-empty, length <= 1000 chars
    CON->>DB: INSERT INTO messages (expense_id, sender_id, content, is_deleted=False)
    DB-->>CON: message.id = 101

    CON->>RL: group_send("expense_{expense_id}", {type: "chat.message", id: 101, sender: {id, first_name, last_name}, content: "Hello everyone!", created_at: "..."})

    RL->>CON: Dispatch event to channel_name_1 (U1)
    RL->>CON: Dispatch event to channel_name_2 (U2)
    CON-->>WS1: {"type":"chat.message","id":101,"sender":{...},"content":"Hello everyone!","created_at":"..."}
    CON-->>WS2: {"type":"chat.message","id":101,"sender":{...},"content":"Hello everyone!","created_at":"..."}
    WS1-->>U1: Message appears in chat (own bubble)
    WS2-->>U2: Message appears in chat (other bubble, instant)

    Note over U1,DB: === DELETE MESSAGE PHASE ===

    U1->>WS1: Clicks delete on message 101
    WS1->>CON: {"type": "chat.delete", "message_id": 101}
    CON->>DB: SELECT message WHERE id=101
    CON->>CON: Verify message.sender_id == token.user_id
    alt Not the sender
        CON-->>WS1: {"type":"chat.error","message":"You can only delete your own messages"}
    end
    CON->>DB: UPDATE messages SET is_deleted=True, updated_at=NOW() WHERE id=101
    CON->>RL: group_send("expense_{expense_id}", {type: "chat.delete", id: 101})
    RL->>CON: Dispatch to both channels
    CON-->>WS1: {"type":"chat.delete","id":101}
    CON-->>WS2: {"type":"chat.delete","id":101}
    WS1-->>U1: Message replaced with "[deleted]"
    WS2-->>U2: Message replaced with "[deleted]"

    Note over U1,DB: === DISCONNECT PHASE ===

    U1->>WS1: Navigates away from page
    WS1->>CON: WebSocket close event
    CON->>RL: group_discard("expense_{expense_id}", channel_name_1)
    Note over CON: No DB cleanup needed
```

---

## SD-04 — Balance Recalculation

```mermaid
sequenceDiagram
    autonumber
    participant T as Trigger<br/>(Expense / Settlement<br/>Create · Edit · Delete)
    participant DRF as Django REST View
    participant BAL as Balance Service
    participant DB as PostgreSQL

    Note over T,DB: === TRIGGERED BY EXPENSE CREATE ===

    T->>DRF: POST /api/groups/{gid}/expenses/ (validated, splits computed)
    DRF->>DB: BEGIN TRANSACTION (atomic block wraps everything below)
    DRF->>DB: INSERT expenses row
    DRF->>DB: INSERT expense_splits rows

    DRF->>BAL: apply_expense_to_balances(expense, splits, op='add')
    loop For each split_i where split_i.user_id != payer_id
        BAL->>BAL: owe_amount = split_i.amount
        BAL->>BAL: u1 = min(payer_id, split_i.user_id)
        BAL->>BAL: u2 = max(payer_id, split_i.user_id)
        BAL->>BAL: if payer_id < split_i.user_id → delta = +owe_amount
        BAL->>BAL: if payer_id > split_i.user_id → delta = -owe_amount
        BAL->>DB: SELECT FOR UPDATE FROM balances WHERE group_id=G AND user1_id=u1 AND user2_id=u2
        alt Row found
            BAL->>DB: UPDATE balances SET net_amount = net_amount + delta
        else Not found
            BAL->>DB: INSERT INTO balances VALUES (G, u1, u2, delta)
        end
    end
    DRF->>DB: COMMIT TRANSACTION
    DRF-->>T: 201 response

    Note over T,DB: === TRIGGERED BY EXPENSE EDIT ===

    T->>DRF: PATCH /api/groups/{gid}/expenses/{id}/
    DRF->>DB: BEGIN TRANSACTION
    DRF->>DB: SELECT expense + old expense_splits (snapshot before edit)
    DRF->>BAL: apply_expense_to_balances(old_expense, old_splits, op='reverse')
    Note over BAL: Reversal applies negative deltas (undoes old effect)
    BAL->>DB: UPDATE balances (reverse old deltas, SELECT FOR UPDATE each row)
    DRF->>DB: UPDATE expenses row with new values
    DRF->>DB: DELETE old expense_splits
    DRF->>DB: INSERT new expense_splits
    DRF->>BAL: apply_expense_to_balances(new_expense, new_splits, op='add')
    BAL->>DB: UPDATE/INSERT balances (apply new deltas)
    DRF->>DB: COMMIT TRANSACTION
    DRF-->>T: 200 response

    Note over T,DB: === TRIGGERED BY EXPENSE DELETE ===

    T->>DRF: DELETE /api/groups/{gid}/expenses/{id}/
    DRF->>DB: BEGIN TRANSACTION
    DRF->>DB: SELECT expense + expense_splits (to know what to reverse)
    DRF->>BAL: apply_expense_to_balances(expense, splits, op='reverse')
    BAL->>DB: UPDATE balances (reverse all deltas, SELECT FOR UPDATE)
    DRF->>DB: UPDATE expenses SET is_deleted=True
    DRF->>DB: COMMIT TRANSACTION
    DRF-->>T: 200 response

    Note over T,DB: === TRIGGERED BY SETTLEMENT CREATE ===

    T->>DRF: POST /api/groups/{gid}/settlements/
    DRF->>DB: BEGIN TRANSACTION
    DRF->>DB: INSERT settlements row
    DRF->>BAL: apply_settlement_to_balance(settlement, op='add')
    BAL->>BAL: u1=min(payer_id,receiver_id), u2=max(payer_id,receiver_id)
    BAL->>BAL: if payer_id < receiver_id → delta = +amount (reduces payer debt)
    BAL->>BAL: if payer_id > receiver_id → delta = -amount (reduces payer debt)
    BAL->>DB: SELECT FOR UPDATE FROM balances WHERE group_id=G AND user1_id=u1 AND user2_id=u2
    BAL->>DB: UPDATE balances SET net_amount = net_amount + delta
    DRF->>DB: COMMIT TRANSACTION
    DRF-->>T: 201 response

    Note over BAL,DB: All four triggers follow the same pattern:<br/>1. Snapshot old state<br/>2. Reverse old effect (if edit/delete)<br/>3. Apply new effect (if create/edit)<br/>All within one atomic() transaction block.
```
