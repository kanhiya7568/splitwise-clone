import { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      onError: (error: unknown) => {
        const msg = (error as { response?: { data?: { error?: string } } })?.response?.data?.error
        toast.error(msg ?? 'Something went wrong')
      },
    },
  },
})

export const qk = {
  me: () => ['me'] as const,
  groups: () => ['groups'] as const,
  group: (id: number) => ['groups', id] as const,
  expenses: (gid: number) => ['expenses', gid] as const,
  expense: (gid: number, eid: number) => ['expenses', gid, eid] as const,
  groupBalances: (gid: number) => ['balances', 'group', gid] as const,
  globalBalances: () => ['balances', 'global'] as const,
  settlements: (gid: number) => ['settlements', gid] as const,
  messages: (eid: number) => ['messages', eid] as const,
}
