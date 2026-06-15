import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { authApi, groupsApi, expensesApi, balancesApi, settlementsApi, chatApi } from '../api'
import { qk, queryClient } from '../lib/queryClient'
import { useAuthStore } from '../store/authStore'

// ── Auth ──────────────────────────────────────────────────────────────
export const useMe = () =>
  useQuery({
    queryKey: qk.me(),
    queryFn: authApi.me,
    enabled: !!useAuthStore.getState().accessToken,
  })

export const useLogin = () =>
  useMutation({
    mutationFn: authApi.login,
    onSuccess: data => {
      useAuthStore.getState().login(data, data.user)
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string; non_field_errors?: string[] } } }
      const msg =
        err?.response?.data?.detail ??
        err?.response?.data?.non_field_errors?.[0] ??
        'Invalid credentials'
      toast.error(msg)
    },
  })

export const useRegister = () =>
  useMutation({
    mutationFn: authApi.register,
    onSuccess: data => {
      useAuthStore.getState().login(data, data.user)
    },
  })

export const useLogout = () =>
  useMutation({
    mutationFn: () => {
      const refresh = localStorage.getItem('refresh_token') ?? ''
      return authApi.logout(refresh)
    },
    onSettled: () => {
      queryClient.clear()
      useAuthStore.getState().logout()
    },
  })

// ── Groups ────────────────────────────────────────────────────────────
export const useGroups = () =>
  useQuery({ queryKey: qk.groups(), queryFn: groupsApi.list })

export const useGroup = (id: number) =>
  useQuery({
    queryKey: qk.group(id),
    queryFn: () => groupsApi.get(id),
    enabled: !!id,
  })

export const useGroupMembers = (id: number) =>
  useQuery({
    queryKey: [...qk.group(id), 'members'],
    queryFn: () => groupsApi.members(id),
    enabled: !!id,
  })

export const useCreateGroup = () =>
  useMutation({
    mutationFn: groupsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.groups() })
      toast.success('Group created!')
    },
  })

export const useInviteMember = (gid: number) =>
  useMutation({
    mutationFn: (email: string) => groupsApi.invite(gid, email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.group(gid) })
      queryClient.invalidateQueries({ queryKey: [...qk.group(gid), 'members'] })
      toast.success('Invitation sent!')
    },
  })

export const useRemoveMember = (gid: number) =>
  useMutation({
    mutationFn: (uid: number) => groupsApi.removeMember(gid, uid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.group(gid) })
      queryClient.invalidateQueries({ queryKey: [...qk.group(gid), 'members'] })
      queryClient.invalidateQueries({ queryKey: qk.groupBalances(gid) })
      toast.success('Member removed')
    },
  })

// ── Expenses ──────────────────────────────────────────────────────────
export const useExpenses = (gid: number, params?: Record<string, string>) =>
  useQuery({
    queryKey: [...qk.expenses(gid), params],
    queryFn: () => expensesApi.list(gid, params),
    enabled: !!gid,
  })

export const useExpense = (gid: number, eid: number) =>
  useQuery({
    queryKey: qk.expense(gid, eid),
    queryFn: () => expensesApi.get(gid, eid),
    enabled: !!gid && !!eid,
  })

const invalidateAfterExpense = (gid: number, eid?: number) => {
  queryClient.invalidateQueries({ queryKey: qk.expenses(gid) })
  if (eid) queryClient.invalidateQueries({ queryKey: qk.expense(gid, eid) })
  queryClient.invalidateQueries({ queryKey: qk.groupBalances(gid) })
  queryClient.invalidateQueries({ queryKey: qk.globalBalances() })
}

export const useCreateExpense = (gid: number) =>
  useMutation({
    mutationFn: (data: unknown) => expensesApi.create(gid, data),
    onSuccess: () => { invalidateAfterExpense(gid); toast.success('Expense added!') },
  })

export const useUpdateExpense = (gid: number, eid: number) =>
  useMutation({
    mutationFn: (data: unknown) => expensesApi.update(gid, eid, data),
    onSuccess: () => { invalidateAfterExpense(gid, eid); toast.success('Expense updated!') },
  })

export const useDeleteExpense = (gid: number) =>
  useMutation({
    mutationFn: (eid: number) => expensesApi.delete(gid, eid),
    onSuccess: () => { invalidateAfterExpense(gid); toast.success('Expense deleted') },
  })

// ── Balances ──────────────────────────────────────────────────────────
export const useGlobalBalances = () =>
  useQuery({ queryKey: qk.globalBalances(), queryFn: balancesApi.global })

export const useGroupBalances = (gid: number, simplified = false) =>
  useQuery<any[], Error>({
    queryKey: [...qk.groupBalances(gid), simplified],
    queryFn: () => (simplified ? balancesApi.simplified(gid) : balancesApi.group(gid)),
    enabled: !!gid,
  })

// ── Settlements ───────────────────────────────────────────────────────
export const useSettlements = (gid: number) =>
  useQuery({
    queryKey: qk.settlements(gid),
    queryFn: () => settlementsApi.list(gid),
    enabled: !!gid,
  })

export const useCreateSettlement = (gid: number) =>
  useMutation({
    mutationFn: (data: { payer_id: number; receiver_id: number; amount: string; note?: string }) =>
      settlementsApi.create(gid, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.settlements(gid) })
      queryClient.invalidateQueries({ queryKey: qk.groupBalances(gid) })
      queryClient.invalidateQueries({ queryKey: qk.globalBalances() })
      toast.success('Settlement recorded!')
    },
  })

// ── Chat ──────────────────────────────────────────────────────────────
export const useMessages = (eid: number) =>
  useQuery({
    queryKey: qk.messages(eid),
    queryFn: () => chatApi.messages(eid),
    enabled: !!eid,
  })
