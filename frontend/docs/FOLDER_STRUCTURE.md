# Folder Structure

```
splitwise-clone/
└── frontend/
    ├── docs/                            ← Phase 6A artifacts (this dir)
    │   ├── FRONTEND_BUILD_PLAN.md
    │   ├── FRONTEND_ROUTE_MAP.md
    │   ├── API_CONTRACT_MAPPING.md
    │   ├── COMPONENT_TREE.md
    │   ├── UI_STATE_FLOW.md
    │   └── FOLDER_STRUCTURE.md
    ├── public/
    │   └── favicon.svg
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── main.tsx                     ← React 19 createRoot entry
        ├── App.tsx                      ← QueryClientProvider + Router + Toaster
        │
        ├── types/                       ← Shared TypeScript interfaces
        │   ├── auth.ts                  ← User, TokenPair
        │   ├── group.ts                 ← Group, GroupMembership, GroupInvitation
        │   ├── expense.ts               ← Expense, ExpenseSplit, SplitType, Category
        │   ├── balance.ts               ← Balance, SimplifiedBalance
        │   ├── settlement.ts            ← Settlement
        │   ├── chat.ts                  ← Message, WsFrame
        │   └── api.ts                   ← PaginatedResponse, ApiError
        │
        ├── lib/                         ← Infrastructure / utilities
        │   ├── axios.ts                 ← Axios instance + interceptors (attach token, refresh retry)
        │   ├── queryClient.ts           ← TanStack Query client config
        │   ├── queryKeys.ts             ← Canonical query key factory
        │   └── utils.ts                 ← cn() (clsx), formatCurrency, formatDate, getInitials
        │
        ├── store/                       ← Zustand stores
        │   ├── authStore.ts             ← user, accessToken, hydrate, login, logout, setAccessToken
        │   ├── uiStore.ts               ← activeModal, modalProps, openModal, closeModal, toggleSidebar
        │   └── chatStore.ts             ← messages, status, connect, disconnect, sendMessage, deleteMessage
        │
        ├── api/                         ← API call functions (axios wrappers)
        │   ├── auth.ts                  ← register, login, logout, refresh, getMe
        │   ├── groups.ts                ← listGroups, getGroup, createGroup, inviteMember, removeMember
        │   ├── expenses.ts              ← listExpenses, getExpense, createExpense, updateExpense, deleteExpense
        │   ├── balances.ts              ← getGlobalBalances, getGroupBalances, getSimplifiedBalances
        │   ├── settlements.ts           ← listSettlements, createSettlement
        │   └── chat.ts                  ← listMessages
        │
        ├── hooks/                       ← Custom React hooks (TanStack Query wrappers)
        │   ├── useAuth.ts               ← useMe, useLogin, useRegister, useLogout
        │   ├── useGroups.ts             ← useGroups, useGroup, useCreateGroup, useInviteMember, useRemoveMember
        │   ├── useExpenses.ts           ← useExpenses, useExpense, useCreateExpense, useUpdateExpense, useDeleteExpense
        │   ├── useBalances.ts           ← useGlobalBalances, useGroupBalances, useSimplifiedBalances
        │   ├── useSettlements.ts        ← useSettlements, useCreateSettlement
        │   ├── useMessages.ts           ← useMessages (REST history)
        │   └── useChatSocket.ts         ← wraps chatStore.connect/disconnect, returns messages + sendMessage + deleteMessage
        │
        ├── components/
        │   ├── ui/                      ← Primitive/design-system components
        │   │   ├── Button.tsx
        │   │   ├── Input.tsx
        │   │   ├── Textarea.tsx
        │   │   ├── Select.tsx
        │   │   ├── Label.tsx
        │   │   ├── Card.tsx
        │   │   ├── Avatar.tsx
        │   │   ├── Badge.tsx
        │   │   ├── Spinner.tsx
        │   │   ├── Skeleton.tsx
        │   │   ├── EmptyState.tsx
        │   │   ├── Modal.tsx
        │   │   ├── ConfirmDialog.tsx
        │   │   ├── Pagination.tsx
        │   │   ├── Tabs.tsx
        │   │   └── Tooltip.tsx
        │   │
        │   ├── layout/                  ← App chrome
        │   │   ├── AppLayout.tsx        ← sidebar + main content area
        │   │   ├── Sidebar.tsx          ← nav links, user menu
        │   │   ├── TopBar.tsx           ← mobile header + hamburger
        │   │   ├── RequireAuth.tsx      ← auth guard (redirects to /login)
        │   │   └── PublicOnly.tsx       ← redirect authenticated users to /
        │   │
        │   ├── modals/                  ← Modal components
        │   │   ├── CreateGroupModal.tsx
        │   │   ├── InviteMembersModal.tsx
        │   │   ├── AddExpenseModal.tsx
        │   │   ├── EditExpenseModal.tsx
        │   │   └── RecordSettlementModal.tsx
        │   │
        │   ├── expense/                 ← Expense-specific components
        │   │   ├── ExpenseForm.tsx      ← shared form (add + edit)
        │   │   ├── ExpenseRow.tsx
        │   │   ├── ExpenseList.tsx
        │   │   ├── ExpenseFilters.tsx
        │   │   ├── SplitTypeSelect.tsx
        │   │   ├── SplitInputs.tsx      ← conditional split field renderer
        │   │   ├── LiveSplitPreview.tsx
        │   │   ├── EqualSplitPreview.tsx
        │   │   ├── UnequalSplitInputs.tsx
        │   │   ├── PercentageSplitInputs.tsx
        │   │   └── SharesSplitInputs.tsx
        │   │
        │   ├── balance/                 ← Balance display components
        │   │   ├── BalanceRow.tsx
        │   │   ├── SimplifiedRow.tsx
        │   │   ├── SimplifiedToggle.tsx
        │   │   └── BalanceSummaryBar.tsx
        │   │
        │   ├── settlement/              ← Settlement components
        │   │   ├── SettlementRow.tsx
        │   │   └── SettlementList.tsx
        │   │
        │   ├── chat/                    ← Chat components
        │   │   ├── ChatPanel.tsx        ← mounts socket, renders list + input
        │   │   ├── MessageList.tsx
        │   │   ├── MessageBubble.tsx
        │   │   └── MessageInput.tsx
        │   │
        │   └── group/                   ← Group-specific components
        │       ├── GroupCard.tsx
        │       ├── GroupAvatar.tsx
        │       ├── MemberRow.tsx
        │       └── MemberAvatarStack.tsx
        │
        └── pages/                       ← Page components (route targets)
            ├── LoginPage.tsx
            ├── RegisterPage.tsx
            ├── DashboardPage.tsx
            ├── GroupsPage.tsx
            ├── GroupDetailPage.tsx
            ├── ExpenseDetailPage.tsx
            ├── BalancesPage.tsx
            ├── SettlementHistoryPage.tsx
            └── NotFoundPage.tsx
```

---

## Key Configuration Files

### `vite.config.ts`
```typescript
// Proxy /api/* and /ws/* to backend on port 8000 during development
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws':  { target: 'ws://localhost:8000', ws: true },
  }
}
```

### `tailwind.config.ts`
```typescript
// Extend with custom design tokens:
// - colors: primary, surface, muted, border, destructive
// - fontFamily: 'Inter' (Google Fonts)
// - borderRadius: custom scale
// - animation: fade-in, slide-up (for modals)
```

### `lib/axios.ts`
```typescript
// baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000'
// withCredentials: false (JWT in header, not cookies)
// Request interceptor: attach Authorization header
// Response interceptor: 401 → silent refresh → retry
```

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000` | WebSocket base URL |
