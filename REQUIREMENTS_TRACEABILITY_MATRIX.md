# REQUIREMENTS_TRACEABILITY_MATRIX.md

> Maps every assignment requirement to: backend files, frontend files, database tables, APIs, and tests.
> Updated after each implementation module is complete.

---

## How to Read This Matrix

| Column | Meaning |
|---|---|
| Requirement | The original assignment requirement |
| FR ID | Functional Requirement ID from AI_CONTEXT.md |
| DB Tables | Database tables involved |
| Backend Files | Django app files implementing this |
| API Endpoint | REST or WebSocket endpoint |
| Frontend Files | React components/pages implementing this |
| Test File | Test file covering this requirement |
| Status | [ ] Not started / [/] In progress / [x] Done |

---

## AUTHENTICATION

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| User Registration | FR-AUTH-01,02,03 | users, token_blacklist_outstandingtoken | authentication/views.py RegisterView, authentication/serializers.py RegisterSerializer, users/managers.py | POST /api/auth/register/ | pages/RegisterPage.tsx, components/ui/Input.tsx | authentication/tests.py RegisterViewTests | [x] |
| User Login | FR-AUTH-04 | users, token_blacklist_outstandingtoken | authentication/views.py LoginView, authentication/serializers.py LoginSerializer | POST /api/auth/login/ | pages/LoginPage.tsx | authentication/tests.py LoginViewTests | [x] |
| JWT Authentication | FR-AUTH-07,08 | token_blacklist_outstandingtoken, token_blacklist_blacklistedtoken | authentication/views.py TokenRefreshView (extends simplejwt) | POST /api/auth/token/refresh/ | api/client.ts (interceptor) | authentication/tests.py TokenRefreshViewTests | [x] |
| Logout | FR-AUTH-06 | token_blacklist_blacklistedtoken | authentication/views.py LogoutView, authentication/serializers.py LogoutSerializer | POST /api/auth/logout/ | store/authStore.ts | authentication/tests.py LogoutViewTests | [x] |
| Protected Routes | FR-AUTH-07 | — | DRF IsAuthenticated (default in base.py REST_FRAMEWORK), AllowAny override on register/login | All protected endpoints | routes/ProtectedRoute.tsx | authentication/tests.py MeViewTests | [x] |

---

## GROUP MANAGEMENT

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Create Groups | FR-GRP-01,02 | groups, group_memberships | groups/services.py create_group, groups/views.py GroupListCreateView | POST /api/groups/ | pages/GroupsPage.tsx | groups/tests.py CreateGroupTests | [x] |
| View Groups | FR-GRP-09 | groups, group_memberships | groups/views.py GroupListCreateView, GroupDetailView | GET /api/groups/, GET /api/groups/{id}/ | pages/GroupsPage.tsx, pages/GroupDetailPage.tsx | groups/tests.py ListGroupsTests, RetrieveGroupTests | [x] |
| Invite Users | FR-GRP-03 | group_memberships, group_invitations | groups/services.py invite_user, groups/views.py GroupInviteView | POST /api/groups/{id}/invite/ | components/groups/InviteModal.tsx | groups/tests.py InviteUserTests | [x] |
| Add Existing Users | FR-GRP-03 | group_memberships | groups/services.py invite_user (existing user branch) | POST /api/groups/{id}/invite/ | components/groups/InviteModal.tsx | groups/tests.py InviteUserTests | [x] |
| Remove Users | FR-GRP-04 | group_memberships | groups/services.py remove_member, groups/views.py RemoveMemberView, groups/permissions.py | DELETE /api/groups/{id}/members/{uid}/ | components/groups/MemberList.tsx | groups/tests.py RemoveMemberTests | [x] |
| Group Details Page | FR-GRP-09 | groups, group_memberships | groups/views.py GroupDetailView | GET /api/groups/{id}/ | pages/GroupDetailPage.tsx | groups/tests.py RetrieveGroupTests | [x] |

---

## EXPENSE MANAGEMENT

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Create Expense | FR-EXP-01,02 | expenses, expense_splits, balances | expenses/views.py, expenses/services.py, balances/services.py | POST /api/groups/{gid}/expenses/ | components/expenses/ExpenseForm.tsx, components/expenses/SplitEditor.tsx | expenses/tests.py | [ ] |
| Edit Expense | FR-EXP-03,04 | expenses, expense_splits, balances | expenses/views.py, balances/services.py | PATCH /api/groups/{gid}/expenses/{id}/ | components/expenses/ExpenseForm.tsx | expenses/tests.py | [ ] |
| Delete Expense | FR-EXP-03,04 | expenses, expense_splits, balances | expenses/views.py, balances/services.py | DELETE /api/groups/{gid}/expenses/{id}/ | components/expenses/ExpenseCard.tsx | expenses/tests.py | [ ] |
| Expense History | FR-EXP-08,09 | expenses, expense_splits | expenses/views.py, expenses/filters.py | GET /api/groups/{gid}/expenses/ | pages/GroupDetailPage.tsx, components/expenses/ExpenseFilters.tsx | expenses/tests.py | [ ] |

---

## SPLIT TYPES

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Split Equally | FR-SPL-01 | expense_splits | expenses/services.py | POST/PATCH /api/groups/{gid}/expenses/ | components/expenses/SplitEditor.tsx | expenses/tests.py | [ ] |
| Split Unequally | FR-SPL-02 | expense_splits | expenses/services.py | POST/PATCH /api/groups/{gid}/expenses/ | components/expenses/SplitEditor.tsx | expenses/tests.py | [ ] |
| Split by Percentage | FR-SPL-03 | expense_splits | expenses/services.py | POST/PATCH /api/groups/{gid}/expenses/ | components/expenses/SplitEditor.tsx | expenses/tests.py | [ ] |
| Split by Shares | FR-SPL-04 | expense_splits | expenses/services.py | POST/PATCH /api/groups/{gid}/expenses/ | components/expenses/SplitEditor.tsx | expenses/tests.py | [ ] |

---

## EXPENSE CHAT

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Real-time messaging | FR-CHT-03 | messages | chat/consumers.py, chat/routing.py | WS /ws/chat/{eid}/ | components/chat/ChatWindow.tsx, hooks/useChat.ts | chat/tests.py | [ ] |
| Messages update instantly | FR-CHT-03 | messages | chat/consumers.py | WS /ws/chat/{eid}/ | hooks/useChat.ts, components/chat/MessageBubble.tsx | chat/tests.py | [ ] |
| Chat history persists | FR-CHT-04,05 | messages | chat/views.py | GET /api/expenses/{eid}/messages/ | components/chat/ChatWindow.tsx | chat/tests.py | [ ] |

---

## BALANCES

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Group-wise balances | FR-BAL-01,02 | balances | balances/views.py, balances/services.py | GET /api/groups/{gid}/balances/ | pages/BalancesPage.tsx, components/balances/BalanceCard.tsx | balances/tests.py | [ ] |
| Individual balance summaries | FR-BAL-05 | balances | balances/views.py | GET /api/balances/ | pages/DashboardPage.tsx | balances/tests.py | [ ] |
| Net amount owed | FR-BAL-05 | balances | balances/views.py | GET /api/balances/ | pages/DashboardPage.tsx | balances/tests.py | [ ] |
| Net amount receivable | FR-BAL-05 | balances | balances/views.py | GET /api/balances/ | pages/DashboardPage.tsx | balances/tests.py | [ ] |
| Simplified balance calculations | FR-BAL-03 | balances | balances/services.py (simplify_debts) | GET /api/groups/{gid}/balances/?view=simplified | components/balances/BalanceToggle.tsx | balances/tests.py | [ ] |

---

## SETTLEMENTS

| Requirement | FR ID | DB Tables | Backend Files | API Endpoint | Frontend Files | Test File | Status |
|---|---|---|---|---|---|---|---|
| Record Payments | FR-SET-01 | settlements, balances | settlements/views.py, balances/services.py | POST /api/groups/{gid}/settlements/ | components/settlements/SettlementForm.tsx | settlements/tests.py | [ ] |
| Settle Debts | FR-SET-01,03 | settlements, balances | settlements/views.py | POST /api/groups/{gid}/settlements/ | components/settlements/SettlementForm.tsx | settlements/tests.py | [ ] |
| Settlement History | FR-SET-06 | settlements | settlements/views.py | GET /api/groups/{gid}/settlements/ | pages/SettlementHistoryPage.tsx | settlements/tests.py | [ ] |

---

## DATABASE

| Requirement | Implementation |
|---|---|
| Relational database only | PostgreSQL (Neon) |
| Proper normalization | All tables in 3NF; no repeated groups; junction table for many-to-many |
| Foreign keys | All FK relationships declared in Django models |
| Transactions where required | `django.db.transaction.atomic()` on all balance updates, expense create/edit/delete, settlement create/edit/delete |

---

## DEPLOYMENT

| Requirement | Implementation | Status |
|---|---|---|
| Publicly accessible application | Vercel (frontend) + Render (backend) | [ ] |
| GitHub repository | Single monorepo at github.com/... | [ ] |

---

## SUBMISSION FILES

| File | Status |
|---|---|
| README.md | [ ] |
| BUILD_PLAN.md | [x] Created |
| AI_CONTEXT.md | [x] Created |
| Key prompts used | [ ] (will go in /prompts directory) |
| REQUIREMENTS_TRACEABILITY_MATRIX.md | [x] Created (skeleton) |
