# Frontend Route Map

## Route Table

| Path | Component | Guard | Description |
|---|---|---|---|
| `/login` | `LoginPage` | Public only | Email/password login |
| `/register` | `RegisterPage` | Public only | New account creation |
| `/` | `DashboardPage` | Auth required | Overview: totals, recent activity |
| `/groups` | `GroupsPage` | Auth required | All groups list |
| `/groups/:groupId` | `GroupDetailPage` | Auth required | Group view: members, expenses, balances |
| `/groups/:groupId/expenses/:expenseId` | `ExpenseDetailPage` | Auth required | Expense split breakdown + chat |
| `/balances` | `BalancesPage` | Auth required | Global balances, simplified toggle |
| `/groups/:groupId/settlements` | `SettlementHistoryPage` | Auth required | Settlement list + record modal |
| `*` | `NotFoundPage` | None | 404 catch-all |

---

## Route Guards

### `<RequireAuth>`
Wraps all protected routes.

```
On mount:
  if no access token in memory:
    if refresh token in localStorage:
      attempt silent refresh → proceed
    else:
      redirect to /login?next=<current-path>
```

### `<PublicOnly>`
Wraps login and register.

```
On mount:
  if authenticated:
    redirect to /
```

---

## Router Structure

```tsx
<BrowserRouter>
  <Routes>
    {/* Public */}
    <Route element={<PublicOnly />}>
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
    </Route>

    {/* Protected — shared layout */}
    <Route element={<RequireAuth />}>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="groups/:groupId" element={<GroupDetailPage />} />
        <Route path="groups/:groupId/expenses/:expenseId" element={<ExpenseDetailPage />} />
        <Route path="balances" element={<BalancesPage />} />
        <Route path="groups/:groupId/settlements" element={<SettlementHistoryPage />} />
      </Route>
    </Route>

    {/* 404 */}
    <Route path="*" element={<NotFoundPage />} />
  </Routes>
</BrowserRouter>
```

---

## Navigation Map (user flows)

```
Login ──────────────────────────────► Dashboard
Register ────────────────────────────► Dashboard
Dashboard ──► Groups Page ──► Group Detail ──► Expense Detail
                                    │
                                    ├──► Balances (group)
                                    └──► Settlement History
Dashboard ──► Balances Page (global)
```

---

## URL Parameter Reference

| Param | Type | Source | Usage |
|---|---|---|---|
| `groupId` | `number` | `/groups/:groupId` | All group-scoped API calls |
| `expenseId` | `number` | `/groups/:groupId/expenses/:expenseId` | Expense fetch, chat WS |
| `?view=simplified` | `string` | Query param on `/api/groups/:gid/balances/` | Balance toggle |
| `?next=` | `string` | Query param on `/login` | Post-login redirect |
