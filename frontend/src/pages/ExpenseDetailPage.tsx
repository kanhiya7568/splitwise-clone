import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Send, Trash2 } from 'lucide-react'
import { useExpense } from '../hooks'
import { useAuthStore } from '../store/authStore'
import { useChatStore } from '../store/chatStore'
import { Card, Avatar, Badge, Skeleton, Button } from '../components/ui'
import { formatCurrency, formatDate, formatTime } from '../lib/utils'

export function ExpenseDetailPage() {
  const { groupId, expenseId } = useParams<{ groupId: string; expenseId: string }>()
  const gid = parseInt(groupId ?? '0')
  const eid = parseInt(expenseId ?? '0')
  const user = useAuthStore(s => s.user)
  const { data: expense, isLoading } = useExpense(gid, eid)

  const { connect, disconnect, messages, status, sendMessage, deleteMessage } = useChatStore()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (eid) { connect(eid) }; return () => { if (eid) disconnect(eid) } }, [eid])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages[eid]])

  const chatMessages = messages[eid] ?? []

  const handleSend = () => {
    if (!input.trim()) return
    sendMessage(eid, input.trim())
    setInput('')
  }

  if (isLoading) return (
    <div className="p-6 space-y-4 max-w-5xl mx-auto">
      <Skeleton className="h-20" /><Skeleton className="h-40" /><Skeleton className="h-64" />
    </div>
  )
  if (!expense) return <div className="p-6 text-zinc-400">Expense not found</div>

  const ICONS: Record<string, string> = { food: '🍔', transport: '🚌', accommodation: '🏨', entertainment: '🎬', utilities: '⚡', other: '📦', general: '💰' }

  return (
    <div className="p-6 max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-4">
          <div className="size-14 bg-surface-2 rounded-2xl flex items-center justify-center text-3xl shrink-0">
            {ICONS[expense.category] ?? '💰'}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{expense.description}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-2xl font-bold text-indigo-300">{formatCurrency(expense.amount)}</span>
              <Badge variant="default">{expense.split_type_display}</Badge>
              <Badge variant="default">{expense.category_display}</Badge>
            </div>
            <p className="text-zinc-400 text-sm mt-1">
              Paid by <span className="text-white">{expense.paid_by.first_name} {expense.paid_by.last_name}</span>
              {' · '}{formatDate(expense.expense_date)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Split breakdown */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Split breakdown</h2>
          <Card className="divide-y divide-white/5">
            {expense.splits.map(split => (
              <div key={split.id} className="flex items-center gap-3 p-4">
                <Avatar user={split.user} size="sm" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">{split.user.first_name} {split.user.last_name}</p>
                  {split.percentage && <p className="text-xs text-zinc-500">{split.percentage}%</p>}
                  {split.shares && <p className="text-xs text-zinc-500">{split.shares} shares</p>}
                </div>
                <p className="font-semibold text-white">{formatCurrency(split.amount)}</p>
              </div>
            ))}
          </Card>
        </div>

        {/* Chat panel */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-white">Discussion</h2>
            <div className="flex items-center gap-1.5">
              <div className={`size-2 rounded-full ${status[eid] === 'open' ? 'bg-emerald-400' : status[eid] === 'connecting' ? 'bg-amber-400' : 'bg-zinc-600'}`} />
              <span className="text-xs text-zinc-500 capitalize">{status[eid] ?? 'disconnected'}</span>
            </div>
          </div>
          <Card className="flex flex-col h-80 lg:h-[calc(100vh-22rem)]">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {chatMessages.length === 0 && (
                <div className="flex items-center justify-center h-full">
                  <p className="text-zinc-500 text-sm">Be the first to comment!</p>
                </div>
              )}
              {chatMessages.map(msg => (
                <div key={msg.id} className={`flex gap-2 ${msg.sender.id === user?.id ? 'flex-row-reverse' : ''}`}>
                  <Avatar user={msg.sender} size="sm" className="shrink-0 mt-0.5" />
                  <div className={`max-w-[75%] ${msg.sender.id === user?.id ? 'items-end' : 'items-start'} flex flex-col gap-0.5`}>
                    <div className={`px-3 py-2 rounded-2xl text-sm ${
                      msg.is_deleted ? 'bg-white/5 text-zinc-500 italic' :
                      msg.sender.id === user?.id ? 'bg-indigo-600 text-white' : 'bg-surface-2 text-zinc-200'
                    }`}>
                      {msg.content}
                    </div>
                    <div className="flex items-center gap-1.5 px-1">
                      <span className="text-[10px] text-zinc-600">{formatTime(msg.created_at)}</span>
                      {!msg.is_deleted && msg.sender.id === user?.id && (
                        <button onClick={() => deleteMessage(eid, msg.id)} className="text-zinc-600 hover:text-rose-400 transition-colors">
                          <Trash2 className="size-3" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
            {/* Input */}
            <div className="border-t border-white/8 p-3 flex gap-2">
              <input
                value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                placeholder="Type a message…"
                className="flex-1 bg-surface-2 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <Button size="sm" onClick={handleSend} disabled={!input.trim() || status[eid] !== 'open'}>
                <Send className="size-4" />
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
