# Component Tree

Notation:
  [P] = Page
  [L] = Layout
  [C] = Container (data-fetching)
  [U] = UI (pure/presentational)
  [M] = Modal
  [H] = Hook

---

## App Root

```
App
├── QueryClientProvider
├── BrowserRouter
│   └── Routes
│       ├── PublicOnly [L]
│       │   ├── LoginPage [P]
│       │   │   └── AuthForm [U]
│       │   └── RegisterPage [P]
│       │       └── AuthForm [U]
│       ├── RequireAuth [L]
│       │   └── AppLayout [L]
│       │       ├── Sidebar [U]
│       │       │   ├── NavLink (Dashboard)
│       │       │   ├── NavLink (Groups)
│       │       │   ├── NavLink (Balances)
│       │       │   └── UserMenu [U]
│       │       └── <Outlet /> → pages below
│       └── NotFoundPage [P]
└── Toaster (Sonner)
```

---

## Dashboard Page

```
DashboardPage [P]
├── BalanceSummaryBar [C]            ← GET /api/balances/
│   ├── StatCard (Total Owed) [U]
│   ├── StatCard (Total Receivable) [U]
│   └── StatCard (Net Balance) [U]
├── RecentGroupsList [C]             ← GET /api/groups/
│   └── GroupCard [U] (×N)
│       └── GroupAvatar [U]
└── RecentExpensesList [C]           ← GET /api/groups/:gid/expenses/ (per group)
    └── ExpenseRow [U] (×N)
```

---

## Groups Page

```
GroupsPage [P]
├── PageHeader [U]
│   └── Button → opens CreateGroupModal
├── GroupGrid [C]                    ← GET /api/groups/
│   ├── GroupCard [U] (×N)
│   │   ├── GroupAvatar [U]
│   │   ├── MemberAvatarStack [U]
│   │   └── Link → /groups/:id
│   └── EmptyState [U]
└── CreateGroupModal [M]
    └── GroupForm [U]
        └── Input (name)
```

---

## Group Detail Page

```
GroupDetailPage [P]
├── GroupHeader [C]                  ← GET /api/groups/:id/
│   ├── GroupAvatar [U]
│   ├── GroupName [U]
│   └── ActionBar [U]
│       ├── Button → InviteMembersModal
│       ├── Button → AddExpenseModal
│       └── Button → RecordSettlementModal
├── TabBar [U]
│   ├── Tab: Expenses
│   ├── Tab: Members
│   ├── Tab: Balances
│   └── Tab: Settlements
└── TabContent [C]
    ├── ExpensesTab [C]              ← GET /api/groups/:gid/expenses/
    │   ├── ExpenseFilters [U]
    │   ├── ExpenseList [U]
    │   │   └── ExpenseRow [U] (×N)
    │   │       ├── CategoryIcon [U]
    │   │       ├── ExpenseInfo [U]
    │   │       ├── SplitBadge [U]
    │   │       └── ContextMenu [U]
    │   │           ├── Edit → EditExpenseModal
    │   │           └── Delete → confirm → DELETE
    │   ├── Pagination [U]
    │   └── EmptyState [U]
    ├── MembersTab [C]               ← GET /api/groups/:id/
    │   └── MemberRow [U] (×N)
    │       ├── Avatar [U]
    │       ├── UserInfo [U]
    │       └── RemoveButton [U] (admin only)
    ├── BalancesTab [C]              ← GET /api/groups/:gid/balances/?view=...
    │   ├── SimplifiedToggle [U]
    │   ├── RawBalanceList [U]
    │   │   └── BalanceRow [U] (×N)
    │   └── SimplifiedBalanceList [U]
    │       └── SimplifiedRow [U] (×N)
    └── SettlementsTab [C]           ← GET /api/groups/:gid/settlements/
        ├── SettlementList [U]
        │   └── SettlementRow [U] (×N)
        └── EmptyState [U]
```

---

## Expense Detail Page

```
ExpenseDetailPage [P]
├── ExpenseHeader [C]                ← GET /api/groups/:gid/expenses/:eid/
│   ├── ExpenseTitle [U]
│   ├── AmountDisplay [U]
│   ├── PayerInfo [U]
│   └── SplitTypeBadge [U]
├── SplitBreakdown [U]
│   └── SplitRow [U] (×N)
│       ├── Avatar [U]
│       └── AmountDisplay [U]
└── ChatPanel [C]                    ← WS + GET /api/expenses/:eid/messages/
    ├── MessageList [U]
    │   └── MessageBubble [U] (×N)
    │       ├── Avatar [U]
    │       ├── MessageContent [U]
    │       └── DeleteButton [U] (own message only)
    ├── TypingIndicator [U]          (future)
    └── MessageInput [U]
        ├── Textarea
        └── SendButton
```

---

## Balances Page

```
BalancesPage [P]
├── GlobalBalanceSummary [C]         ← GET /api/balances/
│   └── BalanceRow [U] (×N)
└── PerGroupBalances [C]             ← GET /api/groups/ then balances per group
    └── GroupBalanceCard [U] (×N)
        └── BalanceRow [U] (×N)
```

---

## Settlement History Page

```
SettlementHistoryPage [P]
├── PageHeader [U]
│   └── Button → RecordSettlementModal
├── SettlementList [C]               ← GET /api/groups/:gid/settlements/
│   ├── SettlementRow [U] (×N)
│   └── EmptyState [U]
└── Pagination [U]
```

---

## Modals

```
CreateGroupModal [M]
└── GroupForm [U]
    └── RHF + Zod validation

InviteMembersModal [M]
└── InviteForm [U]
    ├── EmailInput [U]
    └── SubmitButton [U]

AddExpenseModal [M]
└── ExpenseForm [U]
    ├── DescriptionInput [U]
    ├── AmountInput [U]
    ├── CategorySelect [U]
    ├── DateInput [U]
    ├── SplitTypeSelect [U]
    ├── PaidBySelect [U]
    ├── ParticipantSelector [U]
    ├── SplitInputs [U] (conditional on split type)
    │   ├── EqualSplitPreview [U]
    │   ├── UnequalSplitInputs [U]
    │   ├── PercentageSplitInputs [U]
    │   └── SharesSplitInputs [U]
    └── LiveSplitPreview [U]

EditExpenseModal [M]
└── ExpenseForm [U] (pre-populated)

RecordSettlementModal [M]
└── SettlementForm [U]
    ├── PayerSelect [U]
    ├── ReceiverSelect [U]
    ├── AmountInput [U]
    └── NoteInput [U]
```

---

## Shared / Primitive Components

```
ui/
├── Button [U]
├── Input [U]
├── Textarea [U]
├── Select [U]
├── Label [U]
├── Card [U]
├── Avatar [U]
├── Badge [U]
├── Spinner [U]
├── Skeleton [U]
├── EmptyState [U]
├── Modal [U]          (headless, focus trap)
├── ConfirmDialog [U]
├── Pagination [U]
├── Tabs [U]
└── Tooltip [U]
```
