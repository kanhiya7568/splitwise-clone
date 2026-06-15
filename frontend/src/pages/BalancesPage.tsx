import { useState } from 'react'
import { CheckCircle2, Wallet } from 'lucide-react'
import { useGroups, useGlobalBalances, useGroupBalances } from '../hooks'
import { useAuthStore } from '../store/authStore'
import { Card, Skeleton, EmptyState, Avatar } from '../components/ui'
import { formatCurrency, resolveBalance } from '../lib/utils'
import type { Balance, SimplifiedBalance } from '../types'

export function BalancesPage() {
  const user = useAuthStore(s => s.user)
  const [simplified, setSimplified] = useState(false)
  const { data: groupsData, isLoading: gLoading } = useGroups()
  const { data: globalBalances, isLoading: bLoading } = useGlobalBalances()
  const groups = groupsData?.results ?? []

  let totalOwed = 0, totalReceivable = 0
  if (globalBalances && user) {
    for (const b of globalBalances) {
      const info = resolveBalance(b, user.id)
      if (info.type === 'owe') totalOwed += info.amount
      else if (info.type === 'receivable') totalReceivable += info.amount
    }
  }
  const allSettled = !bLoading && (!globalBalances || globalBalances.every(b => Math.abs(parseFloat(b.net_amount)) < 0.01))

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Balances</h1>
          <p className="text-zinc-400 text-sm mt-0.5">Track what you owe and what's owed to you</p>
        </div>
      </div>

      {/* Summary */}
      {bLoading ? <Skeleton className="h-24 mb-6" /> : (
        <div className="grid grid-cols-2 gap-4 mb-8">
          <Card className="p-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">You owe</p>
            <p className={`text-xl font-bold ${totalOwed > 0 ? 'text-rose-400' : 'text-white'}`}>{formatCurrency(totalOwed)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">You are owed</p>
            <p className={`text-xl font-bold ${totalReceivable > 0 ? 'text-emerald-400' : 'text-white'}`}>{formatCurrency(totalReceivable)}</p>
          </Card>
        </div>
      )}

      {allSettled ? (
        <div className="flex flex-col items-center py-16 gap-4 text-center">
          <CheckCircle2 className="size-16 text-emerald-500" />
          <div>
            <p className="text-white text-lg font-semibold">All settled up! 🎉</p>
            <p className="text-zinc-400 text-sm mt-1">You have no outstanding balances</p>
          </div>
        </div>
      ) : (
        <>
          {/* Per-group balances */}
          {gLoading ? (
            <div className="space-y-4">{[1,2].map(i => <Skeleton key={i} className="h-32" />)}</div>
          ) : (
            <div className="space-y-6">
              {groups.map(g => (
                <GroupBalanceSection key={g.id} groupId={g.id} groupName={g.name} userId={user?.id ?? 0} simplified={simplified} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function GroupBalanceSection({ groupId, groupName, userId, simplified }: {
  groupId: number; groupName: string; userId: number; simplified: boolean
}) {
  const { data: balances, isLoading } = useGroupBalances(groupId, simplified)
  if (isLoading) return <Skeleton className="h-24" />
  if (!balances || balances.length === 0) return null

  const filtered = simplified
    ? (balances as SimplifiedBalance[])
    : (balances as Balance[]).filter(b => Math.abs(parseFloat(b.net_amount)) > 0.01)

  if (filtered.length === 0) return null

  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-400 mb-2 uppercase tracking-wider">{groupName}</h3>
      <Card className="divide-y divide-white/5">
        {simplified
          ? (filtered as SimplifiedBalance[]).map((b, i) => (
            <div key={i} className="flex items-center gap-3 p-4">
              <Avatar user={b.payer} size="sm" />
              <div className="flex-1 text-sm text-zinc-300">
                <span className="text-white">{b.payer.first_name}</span> → <span className="text-white">{b.receiver.first_name}</span>
              </div>
              <span className="text-indigo-300 font-semibold">{formatCurrency(b.amount)}</span>
            </div>
          ))
          : (filtered as Balance[]).map((b, i) => {
            const info = resolveBalance(b, userId)
            return (
              <div key={i} className="flex items-center justify-between p-4">
                <p className="text-sm text-zinc-300">{info.label}</p>
                <span className={`font-semibold text-sm ${info.type === 'receivable' ? 'text-emerald-400' : info.type === 'owe' ? 'text-rose-400' : 'text-zinc-300'}`}>
                  {formatCurrency(info.amount)}
                </span>
              </div>
            )
          })
        }
      </Card>
    </div>
  )
}
