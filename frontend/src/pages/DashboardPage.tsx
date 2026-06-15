import { Link } from 'react-router-dom'
import { Users, Plus } from 'lucide-react'
import { useGroups, useGlobalBalances } from '../hooks'
import { useAuthStore } from '../store/authStore'
import { useUIStore } from '../store/uiStore'
import { StatCard, Card, Button, Skeleton, EmptyState } from '../components/ui'
import { formatCurrency, formatDate, resolveBalance } from '../lib/utils'

export function DashboardPage() {
  const user = useAuthStore(s => s.user)
  const { openModal } = useUIStore()
  const { data: groupsData, isLoading: gLoading } = useGroups()
  const { data: balances, isLoading: bLoading } = useGlobalBalances()

  const groups = groupsData?.results ?? []

  // Compute totals from global balances
  let totalOwed = 0, totalReceivable = 0
  if (balances && user) {
    for (const b of balances) {
      const info = resolveBalance(b, user.id)
      if (info.type === 'owe') totalOwed += info.amount
      else if (info.type === 'receivable') totalReceivable += info.amount
    }
  }
  const net = totalReceivable - totalOwed

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Good to see you, {user?.first_name} 👋</h1>
        <p className="text-zinc-400 text-sm mt-1">Here's your financial overview</p>
      </div>

      {/* Balance summary */}
      {bLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1,2,3].map(i => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="You Owe" value={formatCurrency(totalOwed)} color={totalOwed > 0 ? 'red' : 'default'} />
          <StatCard label="You Are Owed" value={formatCurrency(totalReceivable)} color={totalReceivable > 0 ? 'green' : 'default'} />
          <StatCard label="Net Balance" value={formatCurrency(Math.abs(net))}
            sub={net > 0 ? 'You are owed overall' : net < 0 ? 'You owe overall' : 'All settled!'}
            color={net > 0 ? 'green' : net < 0 ? 'red' : 'default'} />
        </div>
      )}

      {/* Recent groups */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Your Groups</h2>
          <Button size="sm" onClick={() => openModal('create_group')}>
            <Plus className="size-4" /> New Group
          </Button>
        </div>
        {gLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}
          </div>
        ) : groups.length === 0 ? (
          <EmptyState icon={<Users className="size-6" />} title="No groups yet"
            description="Create a group to start splitting expenses"
            action={<Button onClick={() => openModal('create_group')}><Plus className="size-4" /> Create Group</Button>} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {groups.slice(0, 6).map(group => (
              <Link key={group.id} to={`/groups/${group.id}`}>
                <Card className="p-4 hover:border-white/15 transition-all cursor-pointer">
                  <div className="flex items-center gap-3">
                    <div className="size-10 bg-indigo-500/15 rounded-xl flex items-center justify-center text-indigo-300 font-bold text-sm">
                      {group.name[0]?.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-white truncate">{group.name}</p>
                      <p className="text-xs text-zinc-500">{group.member_count ?? 0} members · {formatDate(group.created_at)}</p>
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
        {groups.length > 6 && (
          <div className="mt-3 text-center">
            <Link to="/groups" className="text-sm text-indigo-400 hover:text-indigo-300">View all {groups.length} groups →</Link>
          </div>
        )}
      </div>

      {/* Global balances */}
      {balances && balances.length > 0 && user && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Outstanding Balances</h2>
          <Card className="divide-y divide-white/5">
            {balances.map((b, i) => {
              const info = resolveBalance(b, user.id)
              if (info.type === 'other' || info.amount < 0.01) return null
              return (
                <div key={i} className="flex items-center justify-between p-4">
                  <p className="text-sm text-zinc-300">{info.label}</p>
                  <span className={`font-semibold text-sm ${info.type === 'receivable' ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {formatCurrency(info.amount)}
                  </span>
                </div>
              )
            })}
          </Card>
        </div>
      )}
    </div>
  )
}
