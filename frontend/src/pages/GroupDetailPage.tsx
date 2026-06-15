import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Plus, UserPlus, ArrowLeftRight, MoreHorizontal, Trash2, Edit, CheckCircle2 } from 'lucide-react'
import { useGroup, useGroupMembers, useExpenses, useGroupBalances, useSettlements, useRemoveMember, useDeleteExpense } from '../hooks'
import { useUIStore } from '../store/uiStore'
import { useAuthStore } from '../store/authStore'
import { Card, Button, Avatar, Badge, Skeleton, EmptyState } from '../components/ui'
import { formatCurrency, formatDate, resolveBalance } from '../lib/utils'
import type { Expense, SimplifiedBalance, Balance } from '../types'

type Tab = 'expenses' | 'members' | 'balances' | 'settlements'

export function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = parseInt(groupId ?? '0')
  const [tab, setTab] = useState<Tab>('expenses')
  const [simplified, setSimplified] = useState(false)
  const { openModal } = useUIStore()
  const user = useAuthStore(s => s.user)

  const { data: group, isLoading: gLoading } = useGroup(gid)
  const { data: members } = useGroupMembers(gid)
  const { data: expensesData, isLoading: eLoading } = useExpenses(gid)
  const { data: balancesData, isLoading: bLoading } = useGroupBalances(gid, simplified)
  const { data: settlementsData } = useSettlements(gid)

  const removeMember = useRemoveMember(gid)
  const deleteExpense = useDeleteExpense(gid)

  const expenses = expensesData?.results ?? []
  const settlements = settlementsData?.results ?? []
  const memberList = members ?? []
  const isAdmin = memberList.find(m => m.user.id === user?.id)?.role === 'admin'

  const TABS: { id: Tab; label: string }[] = [
    { id: 'expenses', label: 'Expenses' },
    { id: 'members', label: 'Members' },
    { id: 'balances', label: 'Balances' },
    { id: 'settlements', label: 'Settlements' },
  ]

  if (gLoading) return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-16 w-64" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )

  if (!group) return <div className="p-6 text-zinc-400">Group not found</div>

  return (
    <div className="animate-fade-in">
      {/* Group header */}
      <div className="border-b border-white/8 p-6">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="size-14 bg-indigo-500/15 rounded-2xl flex items-center justify-center text-indigo-300 font-bold text-xl shrink-0">
            {group.name[0]?.toUpperCase()}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{group.name}</h1>
            <p className="text-zinc-400 text-sm mt-0.5">{memberList.length} members</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => openModal('invite_member', { groupId: gid })}>
              <UserPlus className="size-4" /> Invite
            </Button>
            <Button size="sm" variant="outline" onClick={() => openModal('record_settlement', { groupId: gid })}>
              <ArrowLeftRight className="size-4" /> Settle Up
            </Button>
            <Button size="sm" onClick={() => openModal('add_expense', { groupId: gid })}>
              <Plus className="size-4" /> Add Expense
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-white/8">
        <div className="max-w-4xl mx-auto px-6">
          <div className="flex gap-1 overflow-x-auto">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-3.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                  tab === t.id ? 'border-indigo-500 text-indigo-300' : 'border-transparent text-zinc-400 hover:text-white'
                }`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div className="max-w-4xl mx-auto p-6">
        {/* Expenses tab */}
        {tab === 'expenses' && (
          <div className="space-y-3">
            {eLoading ? (
              [1,2,3].map(i => <Skeleton key={i} className="h-16" />)
            ) : expenses.length === 0 ? (
              <EmptyState icon={<span className="text-2xl">💸</span>} title="No expenses yet"
                description="Add the first expense to get started"
                action={<Button onClick={() => openModal('add_expense', { groupId: gid })}><Plus className="size-4" /> Add Expense</Button>} />
            ) : (
              expenses.map(exp => (
                <ExpenseRow key={exp.id} expense={exp} gid={gid} isCreator={exp.created_by.id === user?.id || isAdmin}
                  onEdit={() => openModal('edit_expense', { groupId: gid, expense: exp })}
                  onDelete={() => deleteExpense.mutate(exp.id)} />
              ))
            )}
          </div>
        )}

        {/* Members tab */}
        {tab === 'members' && (
          <Card className="divide-y divide-white/5">
            {memberList.filter(m => m.is_active).map(m => (
              <div key={m.id} className="flex items-center gap-3 p-4">
                <Avatar user={m.user} size="sm" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">{m.user.first_name} {m.user.last_name}</p>
                  <p className="text-xs text-zinc-500">{m.user.email}</p>
                </div>
                {m.role === 'admin' && <Badge variant="default">Admin</Badge>}
                {isAdmin && m.user.id !== user?.id && (
                  <Button size="sm" variant="destructive" onClick={() => removeMember.mutate(m.user.id)}>
                    Remove
                  </Button>
                )}
              </div>
            ))}
          </Card>
        )}

        {/* Balances tab */}
        {tab === 'balances' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-zinc-400">Balance breakdown</p>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-zinc-400">Simplified</span>
                <button onClick={() => setSimplified(v => !v)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${simplified ? 'bg-indigo-500' : 'bg-white/10'}`}>
                  <span className={`absolute top-0.5 left-0.5 size-4 bg-white rounded-full transition-transform ${simplified ? 'translate-x-5' : ''}`} />
                </button>
              </div>
            </div>
            {bLoading ? (
              [1,2,3].map(i => <Skeleton key={i} className="h-14" />)
            ) : !balancesData || balancesData.length === 0 ? (
              <div className="flex flex-col items-center py-16 gap-3 text-center">
                <CheckCircle2 className="size-12 text-emerald-500" />
                <p className="text-white font-medium">All settled up!</p>
                <p className="text-zinc-500 text-sm">No outstanding balances in this group</p>
              </div>
            ) : simplified ? (
              <Card className="divide-y divide-white/5">
                {(balancesData as SimplifiedBalance[]).map((b, i) => (
                  <div key={i} className="flex items-center gap-4 p-4">
                    <Avatar user={b.payer} size="sm" />
                    <div className="flex-1 text-sm">
                      <span className="text-white">{b.payer.first_name}</span>
                      <span className="text-zinc-400"> should pay </span>
                      <span className="text-white">{b.receiver.first_name}</span>
                    </div>
                    <span className="text-indigo-300 font-semibold">{formatCurrency(b.amount)}</span>
                  </div>
                ))}
              </Card>
            ) : (
              <Card className="divide-y divide-white/5">
                {(balancesData as Balance[]).filter(b => Math.abs(parseFloat(b.net_amount)) > 0.01).map((b, i) => {
                  const info = user ? resolveBalance(b, user.id) : { label: `${b.user1.first_name} ↔ ${b.user2.first_name}`, amount: Math.abs(parseFloat(b.net_amount)), type: 'other' as const }
                  return (
                    <div key={i} className="flex items-center justify-between p-4">
                      <p className="text-sm text-zinc-300">{info.label}</p>
                      <span className={`font-semibold text-sm ${info.type === 'receivable' ? 'text-emerald-400' : info.type === 'owe' ? 'text-rose-400' : 'text-zinc-300'}`}>
                        {formatCurrency(info.amount)}
                      </span>
                    </div>
                  )
                })}
              </Card>
            )}
          </div>
        )}

        {/* Settlements tab */}
        {tab === 'settlements' && (
          <div className="space-y-3">
            {settlements.length === 0 ? (
              <EmptyState icon={<ArrowLeftRight className="size-6" />} title="No settlements"
                description="Record settlements when members pay each other"
                action={<Button onClick={() => openModal('record_settlement', { groupId: gid })}><Plus className="size-4" /> Record Settlement</Button>} />
            ) : (
              settlements.filter(s => !s.is_deleted).map(s => (
                <Card key={s.id} className="p-4">
                  <div className="flex items-center gap-3">
                    <Avatar user={s.payer} size="sm" />
                    <div className="flex-1 text-sm">
                      <span className="text-white font-medium">{s.payer.first_name}</span>
                      <span className="text-zinc-400"> paid </span>
                      <span className="text-white font-medium">{s.receiver.first_name}</span>
                    </div>
                    <div className="text-right">
                      <p className="text-emerald-400 font-semibold">{formatCurrency(s.amount)}</p>
                      <p className="text-xs text-zinc-500">{formatDate(s.created_at)}</p>
                    </div>
                  </div>
                  {s.note && <p className="text-xs text-zinc-500 mt-2 pl-11">{s.note}</p>}
                </Card>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ExpenseRow({ expense, gid, isCreator, onEdit, onDelete }: {
  expense: Expense; gid: number; isCreator: boolean; onEdit: () => void; onDelete: () => void
}) {
  const [menu, setMenu] = useState(false)
  const ICONS: Record<string, string> = { food: '🍔', transport: '🚌', accommodation: '🏨', entertainment: '🎬', utilities: '⚡', other: '📦', general: '💰' }

  return (
    <Card className="p-4 hover:border-white/15 transition-all">
      <div className="flex items-center gap-3">
        <div className="size-10 bg-surface-2 rounded-xl flex items-center justify-center text-lg shrink-0">
          {ICONS[expense.category] ?? '💰'}
        </div>
        <Link to={`/groups/${gid}/expenses/${expense.id}`} className="flex-1 min-w-0">
          <p className="font-medium text-white truncate">{expense.description}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-zinc-500">{formatDate(expense.expense_date)}</span>
            <span className="text-xs text-zinc-600">·</span>
            <span className="text-xs text-zinc-500">Paid by {expense.paid_by.first_name}</span>
            <Badge variant="default" className="text-[10px] px-1.5 py-0">{expense.split_type_display}</Badge>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <p className="font-semibold text-white">{formatCurrency(expense.amount)}</p>
          {isCreator && (
            <div className="relative">
              <Button size="sm" variant="ghost" onClick={() => setMenu(v => !v)}>
                <MoreHorizontal className="size-4" />
              </Button>
              {menu && (
                <div className="absolute right-0 top-8 bg-surface-2 border border-white/10 rounded-lg shadow-xl z-10 py-1 min-w-32">
                  <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-zinc-300 hover:bg-white/5"
                    onClick={() => { onEdit(); setMenu(false) }}>
                    <Edit className="size-3.5" /> Edit
                  </button>
                  <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-rose-400 hover:bg-rose-500/10"
                    onClick={() => { onDelete(); setMenu(false) }}>
                    <Trash2 className="size-3.5" /> Delete
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
