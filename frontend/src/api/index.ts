import api from '../lib/axios'
import type {
  User, Group, GroupMember, Expense, Balance, SimplifiedBalance,
  Settlement, Message, TokenPair, PaginatedResponse
} from '../types'

// ── Auth ──────────────────────────────────────────────────────────────
export const authApi = {
  register: (d: { email: string; password: string; first_name: string; last_name: string }) =>
    api.post<TokenPair & { user: User }>('/api/auth/register/', d).then(r => r.data),
  login: (d: { email: string; password: string }) =>
    api.post<TokenPair & { user: User }>('/api/auth/login/', d).then(r => r.data),
  logout: (refresh: string) =>
    api.post('/api/auth/logout/', { refresh }),
  me: () => api.get<User>('/api/auth/me/').then(r => r.data),
}

// ── Groups ────────────────────────────────────────────────────────────
export const groupsApi = {
  list: () => api.get<PaginatedResponse<Group>>('/api/groups/').then(r => r.data),
  create: (name: string) => api.post<Group>('/api/groups/', { name }).then(r => r.data),
  get: (id: number) => api.get<Group>(`/api/groups/${id}/`).then(r => r.data),
  members: (id: number) => api.get<GroupMember[]>(`/api/groups/${id}/members/`).then(r => r.data),
  invite: (id: number, email: string) =>
    api.post<{ message: string }>(`/api/groups/${id}/invite/`, { email }).then(r => r.data),
  removeMember: (id: number, uid: number) =>
    api.delete(`/api/groups/${id}/members/${uid}/`),
}

// ── Expenses ──────────────────────────────────────────────────────────
export const expensesApi = {
  list: (gid: number, params?: Record<string, string>) =>
    api.get<PaginatedResponse<Expense>>(`/api/groups/${gid}/expenses/`, { params }).then(r => r.data),
  get: (gid: number, eid: number) =>
    api.get<Expense>(`/api/groups/${gid}/expenses/${eid}/`).then(r => r.data),
  create: (gid: number, data: unknown) =>
    api.post<Expense>(`/api/groups/${gid}/expenses/`, data).then(r => r.data),
  update: (gid: number, eid: number, data: unknown) =>
    api.patch<Expense>(`/api/groups/${gid}/expenses/${eid}/edit/`, data).then(r => r.data),
  delete: (gid: number, eid: number) =>
    api.delete(`/api/groups/${gid}/expenses/${eid}/delete/`),
}

// ── Balances ──────────────────────────────────────────────────────────
export const balancesApi = {
  global: () => api.get<Balance[]>('/api/balances/').then(r => r.data),
  group: (gid: number) =>
    api.get<Balance[]>(`/api/groups/${gid}/balances/`).then(r => r.data),
  simplified: (gid: number) =>
    api.get<SimplifiedBalance[]>(`/api/groups/${gid}/balances/`, { params: { view: 'simplified' } }).then(r => r.data),
}

// ── Settlements ───────────────────────────────────────────────────────
export const settlementsApi = {
  list: (gid: number) =>
    api.get<PaginatedResponse<Settlement>>(`/api/groups/${gid}/settlements/`).then(r => r.data),
  create: (gid: number, data: { payer_id: number; receiver_id: number; amount: string; note?: string }) =>
    api.post<Settlement>(`/api/groups/${gid}/settlements/`, data).then(r => r.data),
}

// ── Chat ──────────────────────────────────────────────────────────────
export const chatApi = {
  messages: (eid: number) =>
    api.get<PaginatedResponse<Message>>(`/api/expenses/${eid}/messages/`).then(r => r.data),
}
