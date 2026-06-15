# Frontend Build Plan — Splitwise Clone

## Tech Stack

| Concern | Library | Version |
|---|---|---|
| Framework | React | 19 |
| Language | TypeScript | 5.x |
| Build Tool | Vite | 6.x |
| Styling | Tailwind CSS | 4.x |
| Routing | React Router DOM | 7.x |
| Global State | Zustand | 5.x |
| Server State | TanStack Query | 5.x |
| Forms | React Hook Form | 7.x |
| Validation | Zod | 3.x |
| HTTP | Axios | 1.x |
| Realtime | Native WebSocket API | — |
| Icons | Lucide React | — |
| Notifications | Sonner | 1.x |

---

## Build Phases

### Phase 6B — Project Scaffold
- `npm create vite@latest` with React + TypeScript template
- Install all dependencies
- Configure `tailwind.config.ts`, `vite.config.ts`, `tsconfig.json`
- Configure Axios base URL + interceptors (token attach + refresh retry)
- Configure TanStack Query `QueryClient`
- Configure Zustand stores (auth, UI, chat)
- Configure React Router with route guards
- Configure Sonner toaster

### Phase 6C — Design System
- `src/styles/globals.css` — Tailwind base + custom tokens
- Color palette (dark/light tokens, accent, destructive, muted)
- Typography scale
- Shared primitive components:
  - `Button`, `Input`, `Textarea`, `Label`
  - `Card`, `Avatar`, `Badge`, `Spinner`
  - `Modal`, `Drawer`
  - `Skeleton`
  - `EmptyState`

### Phase 6D — Auth Layer
- Login page
- Register page
- JWT storage in memory (access) + `localStorage` (refresh)
- Axios interceptor: attach `Authorization: Bearer <token>`
- Axios interceptor: auto-refresh on 401
- Protected route wrapper (`<RequireAuth>`)
- Auth store hydration on app start

### Phase 6E — Core Pages
Build pages in dependency order:

1. **Dashboard** — totals, recent groups, recent expenses
2. **Groups Page** — list, create group modal
3. **Group Detail Page** — members, expenses, balances, settlements, invite, chat
4. **Expense Detail Page** — split breakdown, chat panel
5. **Balances Page** — global + per-group, simplified toggle
6. **Settlement History Page** — list + record settlement modal
7. **404 Page**

### Phase 6F — Modals
- Create Group Modal
- Invite Members Modal
- Add Expense Modal (4 split types + live preview)
- Edit Expense Modal
- Record Settlement Modal

### Phase 6G — Chat (WebSocket)
- `useChatSocket` hook
- Per-expense chat panel with history
- Send message
- Delete own message
- Reconnect logic (exponential backoff)

### Phase 6H — Polish
- Responsive layout audit (mobile / tablet / desktop)
- Skeleton loading states on all data-fetching components
- Empty states with actionable CTAs
- Transition animations (page enter, modal open/close)
- Accessibility: keyboard navigation, ARIA labels, focus traps in modals

---

## Acceptance Criteria

| Criteria | Done |
|---|---|
| All 7 protected pages render | ☐ |
| All 5 modals functional | ☐ |
| All 4 split types work in expense form | ☐ |
| Simplified balance toggle works | ☐ |
| WebSocket chat connects and broadcasts | ☐ |
| Token refresh is transparent | ☐ |
| Mobile layout is usable | ☐ |
| No TypeScript errors | ☐ |
| No console errors in production build | ☐ |
