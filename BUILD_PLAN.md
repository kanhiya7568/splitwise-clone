# BUILD_PLAN.md — Splitwise Clone

> This document describes the complete product research, architecture plan, AI collaboration process, and implementation roadmap for the Splitwise-inspired expense splitting application.

---

## Part 1 — Product Research

### Splitwise Analysis

Splitwise is a shared expense management platform founded in 2011. Its core function is to track who paid for shared expenses and calculate the minimum number of payments needed for everyone to settle their debts.

**What makes Splitwise valuable:**
- Eliminates social awkwardness of asking for money
- Automates complex multi-person debt calculations
- Provides transparent audit trail of all shared expenses
- Minimizes total transactions needed through debt simplification

**Business model:** Freemium. Free tier has core features; Pro tier adds receipt scanning, charts, ad-free experience.

### Workflows Discovered

| Workflow | Steps |
|---|---|
| Onboarding | Register → Land on dashboard with empty state → Create first group |
| Group lifecycle | Create → Invite members → Add expenses → View balances → Settle → (Delete when done) |
| Expense lifecycle | Add → (Edit if needed) → (Delete if wrong) → Discuss in chat → Settle up |
| Settlement lifecycle | View balance → Record payment → Verify balance updated |

### Product Assumptions Made
1. Single currency (no multi-currency for MVP)
2. One payer per expense (simplest correct model)
3. No payment gateway; all settlements are manual records
4. No email verification; immediate login after register
5. No push notifications; real-time limited to expense chat
6. Balances are per-group; global view is aggregate

---

## Part 2 — Architecture

### Tech Stack

| Component | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Styling | TailwindCSS |
| State | Zustand (auth/UI) + TanStack Query (server state) |
| Backend | Django 5 + Django REST Framework |
| Real-Time | Django Channels 4 |
| Database | PostgreSQL (Neon) |
| Cache/Broker | Redis (Upstash) |
| Auth | djangorestframework-simplejwt |
| Deployment | Vercel + Render + Neon + Upstash |

### Database Schema (Summary)

| Table | Key Columns |
|---|---|
| `users` | id, email (UK), first_name, last_name, password_hash |
| `groups` | id, name, created_by_id (FK), is_deleted |
| `group_memberships` | id, group_id (FK), user_id (FK), role, is_active |
| `group_invitations` | id, group_id (FK), email, invited_by_id (FK), status |
| `expenses` | id, group_id (FK), paid_by_id (FK), description, amount, category, expense_date, split_type, is_deleted |
| `expense_splits` | id, expense_id (FK), user_id (FK), amount, percentage, shares |
| `balances` | id, group_id (FK), user1_id (FK), user2_id (FK), net_amount |
| `settlements` | id, group_id (FK), payer_id (FK), receiver_id (FK), amount, note, is_deleted |
| `messages` | id, expense_id (FK), sender_id (FK), content, is_deleted |
| `blacklisted_tokens` | id, user_id (FK), token, expires_at |

**Key constraints:**
- `balances`: UNIQUE(group_id, user1_id, user2_id) + CHECK(user1_id < user2_id)
- `expenses.amount`: CHECK(0 < amount <= 999999.99)
- `group_memberships`: UNIQUE(group_id, user_id)

### API Design (Endpoint Summary)

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/auth/register/ | Register user |
| POST | /api/auth/login/ | Login |
| POST | /api/auth/logout/ | Logout + blacklist token |
| POST | /api/auth/token/refresh/ | Refresh access token |
| GET | /api/auth/me/ | Current user info |
| GET/POST | /api/groups/ | List/Create groups |
| GET/PATCH/DELETE | /api/groups/{id}/ | Group detail/update/delete |
| GET | /api/groups/{id}/members/ | List members |
| POST | /api/groups/{id}/invite/ | Invite by email |
| DELETE | /api/groups/{id}/members/{uid}/ | Remove member |
| GET/POST | /api/groups/{gid}/expenses/ | List/Create expenses |
| GET/PATCH/DELETE | /api/groups/{gid}/expenses/{id}/ | Expense detail/update/delete |
| GET | /api/groups/{gid}/balances/ | Group balances (raw/simplified) |
| GET | /api/balances/ | Global balance across all groups |
| GET/POST | /api/groups/{gid}/settlements/ | List/Create settlements |
| GET/PATCH/DELETE | /api/groups/{gid}/settlements/{id}/ | Settlement detail/update/delete |
| GET | /api/expenses/{eid}/messages/ | Chat history (REST) |
| DELETE | /api/expenses/{eid}/messages/{id}/ | Delete own message |
| WS | /ws/chat/{eid}/?token= | Real-time chat |

### Frontend Structure

```
src/
├── api/          # Axios calls per domain
├── components/   # Reusable UI + domain components
├── pages/        # One file per screen
├── store/        # Zustand stores
├── hooks/        # React Query + WS hooks
├── types/        # TypeScript interfaces
└── utils/        # Formatters, validators, WS manager
```

### Backend Structure

```
apps/
├── authentication/  # JWT auth
├── users/           # Custom User model
├── groups/          # Group + Membership + Invitation
├── expenses/        # Expense CRUD + split service
├── balances/        # Cached balances + simplification
├── settlements/     # Settlement CRUD
└── chat/            # Messages REST + WS consumer
```

### Deployment Plan

```
GitHub (monorepo)
├── /frontend  → Vercel (auto-deploy on push to main)
└── /backend   → Render (Daphne ASGI server)
                    ↓ connects to
               Neon PostgreSQL + Upstash Redis
```

---

## Part 3 — AI Collaboration Process

### Phase 1 — Research
- AI researched Splitwise product, user personas, workflows, core entities, and the debt simplification algorithm from public sources
- Identified 3 personas, 7 core workflows, 8 screens, and 9 core entities

### Phase 2 — Discovery Interview
- AI conducted structured 11-batch interview (88 questions) covering: Auth, Groups, Expenses, Splits, Balances, Settlements, Chat, API Design, Frontend, Security, Deployment
- User reviewed all questions and provided comprehensive approved decisions

### Phase 3 — Documentation
- AI generated AI_CONTEXT.md (28 sections, ~1,400 lines) as single source of truth
- AI generated BUILD_PLAN.md (this document)
- AI generated REQUIREMENTS_TRACEABILITY_MATRIX.md (skeleton)
- AI generated complete API contracts, ER diagram, sequence diagrams

### Phase 4 — Technical Design Review
- All design artifacts presented to user for approval before any code is written
- No assumptions made post-interview; all decisions traceable to user input

### Key Decisions Made During Collaboration

| Decision | Made By | Reasoning |
|---|---|---|
| balance(user1_id < user2_id) constraint | AI | Prevents duplicate pairs; single source of truth per pair |
| Greedy O(n log n) simplification | AI | Feasible for groups ≤ 100; true min-cost flow is NP-hard |
| WebSocket auth via query param | AI | Browser WebSocket API limitation — no custom headers |
| Daphne over Gunicorn | AI | Gunicorn is WSGI; Django Channels requires ASGI |
| Soft deletes on all financial records | AI | Audit trail; balance reversal always possible |
| Separate Settlement entity | User | Cleaner model; different business logic from expenses |

---

## Part 4 — Trade-offs

### Simplifications Made
| Area | Simplification | Production Alternative |
|---|---|---|
| Balance caching | Cached table with transactional updates | Event sourcing with full audit log replay |
| Token storage | localStorage for access token | httpOnly cookie (full CSRF protection) |
| Debt simplification | Greedy algorithm | Network flow optimization (NP-hard) |
| Concurrency | DB transactions + last-write-wins | Optimistic locking with user-visible conflict |
| Testing | Model + API + algorithm tests | Full coverage with integration + E2E tests |

### Hardcoded Choices
- Single currency (no currency conversion)
- Max 100 members per group (business rule)
- Max 1000 chars per message
- Max expense amount: 999,999.99
- Rate limit: 100 req/hour/user
- Page size: 20 items (max 100)
- Access token: 60 min; Refresh token: 7 days

### Intentionally Avoided
- Email verification (adds complexity; not in scope)
- Recurring expenses (not in scope)
- Multi-admin groups (single admin simplifies permission logic)
- Offline support (adds PWA complexity)
- Real-time balance updates via WebSocket (only chat is real-time; balances fetched on demand)

### What Would Improve with More Time
- End-to-end tests with Playwright
- CI/CD pipeline with GitHub Actions
- Docker Compose for local development parity
- Redis caching for frequently read balance queries
- Account merging when pending-invite user registers
- Email notifications on new expense or settlement

---

## Part 5 — Implementation Roadmap

### Module Order (as specified in assignment)

| # | Module | Description |
|---|---|---|
| 1 | Backend setup | Django project, settings, PostgreSQL, Redis, CORS |
| 2 | Authentication | Register, login, logout, token refresh, blacklist |
| 3 | Database models | All 10 models with migrations |
| 4 | Group APIs | CRUD + invite + remove member |
| 5 | Expense APIs | CRUD + filtering + pagination |
| 6 | Split algorithms | Equal, unequal, percentage, shares services |
| 7 | Balance calculations | Balance service, update triggers |
| 8 | Settlement logic | Settlement CRUD + balance updates |
| 9 | WebSocket chat | Django Channels consumer + routing |
| 10 | Frontend setup | Vite + React + TS + Tailwind + React Query + Zustand |
| 11 | Authentication UI | Login/Register pages + protected routes |
| 12 | Groups UI | Group list, detail, invite modal, member management |
| 13 | Expenses UI | Expense list, create/edit form, all split type editors |
| 14 | Balances UI | Raw/simplified toggle, balance cards |
| 15 | Settlements UI | Settlement form, history page |
| 16 | Chat UI | ChatWindow, MessageBubble, real-time WebSocket |
| 17 | Testing | Model, algorithm, API tests |
| 18 | Deployment | Vercel, Render, Neon, Upstash setup |

### Post-Module Checklist (after each module)
- [ ] Update AI_CONTEXT.md Section 28 if architecture changed
- [ ] Update REQUIREMENTS_TRACEABILITY_MATRIX.md with implemented files
- [ ] Write tests for the module
- [ ] Verify no assignment requirement is left unaddressed
- [ ] Commit to GitHub with descriptive message
