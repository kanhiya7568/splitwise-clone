# FRONTEND_READINESS_REPORT.md
## Phase 6A Architecture Readiness Assessment

---

## Overall Verdict

**IS THE FRONTEND ARCHITECTURE READY FOR IMPLEMENTATION?**

> ## ⚠️  NO — NOT YET READY
>
> 5 Critical issues must be resolved before Phase 6B begins.
> 8 Major issues should be resolved or formally accepted before implementation.

---

## Blocker Assessment

### Blockers That Will Break the App At Runtime

| Issue | Consequence If Unresolved |
|---|---|
| CRITICAL-01: Balance backend missing | 3 pages (Dashboard, Balances, Group Detail balances tab) return 404 |
| CRITICAL-02: net_amount interpretation | Balance UI displays meaningless signed numbers instead of "you owe / owed" |
| CRITICAL-03: Settlement endpoints missing | No edit/delete of settlements possible from frontend |
| CRITICAL-04: Group endpoints missing | No rename, no delete group, members fetched from wrong URL |
| CRITICAL-05: WS stale token on reconnect | Chat drops permanently after token expiry; may trigger incorrect logout |

### Blockers That Will Fail Code Review

| Issue | Consequence If Unresolved |
|---|---|
| MAJOR-01: Non-serializable Zustand state | Instant red flag in any senior code review |
| MAJOR-04: Manual splits state + RHF | Dirty-state bugs, broken form reset, known interview pitfall |
| MAJOR-06: No ErrorBoundary | Any render error crashes entire app — unacceptable for production |

---

## Required Actions Before Phase 6B

### Backend (must be done first)

1. **Implement apps/balances/views.py** with:
   - `GlobalBalancesView` — GET /api/balances/ (all user's balances across groups)
   - `GroupBalancesView` — GET /api/groups/{gid}/balances/ (raw pairwise)
   - `GroupSimplifiedBalancesView` — GET /api/groups/{gid}/balances/?view=simplified
2. **Implement apps/balances/serializers.py** — BalanceSerializer, SimplifiedBalanceSerializer
3. **Update apps/balances/urls.py** — wire the 3 endpoints

### Frontend Documentation Updates (before any code)

4. **Update API_CONTRACT_MAPPING.md** — add settlement detail/edit/delete, group rename/delete, members endpoint
5. **Update UI_STATE_FLOW.md** — add resolveBalance() algorithm, WebSocket reconnect token strategy, 5 missing cache invalidations, empty states for chat/balances
6. **Update COMPONENT_TREE.md** — add mobile tab layout for ExpenseDetailPage, ErrorBoundary wrapping
7. **Update FOLDER_STRUCTURE.md** — add 6 missing components, ErrorBoundary, socketRegistry pattern

### Architecture Decisions to Formalise

8. Confirm: Remove SettlementHistoryPage as separate route (MAJOR-07)
9. Confirm: useFieldArray for ExpenseForm splits (MAJOR-04)
10. Confirm: module-level socketRegistry for WebSocket instances (MAJOR-01)
11. Confirm: useSuspenseQuery adoption vs manual isLoading branching (MINOR-09)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Balance backend not ready at Phase 6B start | High | High | Build balances backend NOW; it is 3 view files |
| net_amount interpretation bug ships | High | High | resolveBalance() utility is simple; do it in Phase 6B scaffold |
| ExpenseForm splits regression | Medium | High | useFieldArray + Zod superRefine is the correct pattern |
| WS token expiry on reconnect causes logout | Medium | High | Proactive refresh before reconnect |
| Mobile layout breaks interview demo | Medium | Medium | Define layouts before coding begins |
| Settlement edit/delete not discoverable | High | Low | UX oversight; easy to add once endpoints are in mapping |

---

## Suggested Improvements (Nice-to-Have)

| Improvement | Benefit | Effort |
|---|---|---|
| useSuspenseQuery + Suspense boundaries | Cleaner code, signals React 19 mastery | Low |
| "All settled up!" green state | High-impact Splitwise-authentic moment | Low |
| Optimistic updates on message send | Chat feels instant | Medium |
| Group rename inline edit (double-click name) | Premium UX | Low |
| Expense search / text filter | Very Splitwise-like | Medium |
| Dark mode toggle | Design system already supports it with Tailwind | Medium |
| PWA manifest | App installable on mobile | Low |

---

## Phase 6B Prerequisites Checklist

Before any React code is written, confirm all of the following:

- [ ] apps/balances/views.py implemented and manually tested (curl)
- [ ] API_CONTRACT_MAPPING.md updated with all missing endpoints
- [ ] UI_STATE_FLOW.md updated with resolveBalance(), WS token refresh strategy, empty states, and cache invalidation gaps
- [ ] COMPONENT_TREE.md updated with mobile layouts and ErrorBoundary placements
- [ ] FOLDER_STRUCTURE.md updated with all missing components
- [ ] Architecture decisions confirmed: socketRegistry, useFieldArray, SettlementHistoryPage removal

---

## Final Recommendation

The Phase 6A documentation is a **solid foundation** with correct overall architecture.
The tech stack, folder structure, routing strategy, and Zustand/TanStack Query split
are all appropriate for an interview-quality submission.

However, **5 critical issues** — 1 backend gap and 4 API contract omissions — mean
that beginning implementation now would result in broken pages, incorrect UI logic,
and an unstable WebSocket experience.

**Recommended next step:**

1. Resolve CRITICAL-01 (balance backend) — estimated 2-3 hours of backend work.
2. Update all 4 documentation files (estimated 30 minutes).
3. Return with updated docs for a second review.
4. Proceed to Phase 6B with confidence.

The 8 Major issues are resolvable during implementation if the architecture decisions
are formalised first. The 9 Minor issues are polish items that can be addressed in Phase 6H.
