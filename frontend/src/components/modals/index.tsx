import React from 'react'
import { useForm, useFieldArray, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Trash2, Check } from 'lucide-react'
import { Modal, Button, Input, Select, Textarea, Avatar, Badge } from '../ui'
import { useUIStore } from '../../store/uiStore'
import {
  useCreateGroup, useInviteMember, useCreateExpense, useUpdateExpense,
  useCreateSettlement, useGroupMembers,
} from '../../hooks'
import { formatCurrency, CATEGORIES, SPLIT_TYPES } from '../../lib/utils'
import type { Expense, GroupMember } from '../../types'

// ─── Create Group ─────────────────────────────────────────────────────

const createGroupSchema = z.object({ name: z.string().min(1, 'Name is required').max(100) })
type CreateGroupForm = z.infer<typeof createGroupSchema>

function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { register, handleSubmit, formState: { errors }, reset } = useForm<CreateGroupForm>({
    resolver: zodResolver(createGroupSchema),
  })
  const create = useCreateGroup()
  const onSubmit = async (data: CreateGroupForm) => {
    await create.mutateAsync(data.name)
    reset(); onClose()
  }
  return (
    <Modal open={open} onClose={onClose} title="Create Group">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input label="Group name" placeholder="e.g. Goa Trip 2024" error={errors.name?.message} {...register('name')} />
        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create Group</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Invite Members ───────────────────────────────────────────────────

const inviteSchema = z.object({ email: z.string().email('Enter a valid email') })
type InviteForm = z.infer<typeof inviteSchema>

function InviteMemberModal({ open, onClose, groupId }: { open: boolean; onClose: () => void; groupId: number }) {
  const { register, handleSubmit, formState: { errors }, reset } = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
  })
  const invite = useInviteMember(groupId)
  const onSubmit = async (data: InviteForm) => {
    await invite.mutateAsync(data.email)
    reset(); onClose()
  }
  return (
    <Modal open={open} onClose={onClose} title="Invite Member">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input label="Email address" placeholder="friend@example.com" error={errors.email?.message} {...register('email')} />
        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={invite.isPending}>Send Invite</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Expense Form (shared for Add + Edit) ────────────────────────────

const splitEntrySchema = z.object({
  user_id: z.number(),
  amount: z.string().optional(),
  percentage: z.string().optional(),
  shares: z.string().optional(),
})

const expenseSchema = z.object({
  description: z.string().min(1, 'Description required'),
  amount: z.string().refine(v => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Amount must be > 0'),
  category: z.string().default('general'),
  expense_date: z.string().min(1, 'Date required'),
  split_type: z.enum(['equal', 'unequal', 'percentage', 'shares']),
  paid_by: z.number().optional(),
  splits: z.array(splitEntrySchema).min(1, 'Add at least one participant'),
}).superRefine((data, ctx) => {
  const total = parseFloat(data.amount)
  if (isNaN(total)) return
  if (data.split_type === 'unequal') {
    const sum = data.splits.reduce((a, s) => a + parseFloat(s.amount ?? '0'), 0)
    if (Math.abs(sum - total) > 0.01) ctx.addIssue({ code: 'custom', path: ['splits'], message: `Split amounts must sum to ${formatCurrency(total)} (currently ${formatCurrency(sum)})` })
  }
  if (data.split_type === 'percentage') {
    const sum = data.splits.reduce((a, s) => a + parseFloat(s.percentage ?? '0'), 0)
    if (Math.abs(sum - 100) > 0.01) ctx.addIssue({ code: 'custom', path: ['splits'], message: `Percentages must sum to 100% (currently ${sum.toFixed(2)}%)` })
  }
  if (data.split_type === 'shares') {
    const sum = data.splits.reduce((a, s) => a + parseFloat(s.shares ?? '0'), 0)
    if (sum <= 0) ctx.addIssue({ code: 'custom', path: ['splits'], message: 'Total shares must be > 0' })
  }
})

type ExpenseFormData = z.infer<typeof expenseSchema>

function ExpenseFormModal({
  open, onClose, groupId, members, expense, title,
}: {
  open: boolean; onClose: () => void; groupId: number
  members: GroupMember[]; expense?: Expense; title: string
}) {
  const today = new Date().toISOString().split('T')[0]
  const activeMembers = members.filter(m => m.is_active)

  const form = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseSchema),
    defaultValues: expense ? {
      description: expense.description,
      amount: expense.amount,
      category: expense.category,
      expense_date: expense.expense_date,
      split_type: expense.split_type as 'equal' | 'unequal' | 'percentage' | 'shares',
      paid_by: expense.paid_by.id,
      splits: expense.splits.map(s => ({
        user_id: s.user.id,
        amount: s.amount,
        percentage: s.percentage ?? undefined,
        shares: s.shares ?? undefined,
      })),
    } : {
      description: '', amount: '', category: 'general',
      expense_date: today, split_type: 'equal', splits: [],
    },
  })

  const { fields, append, remove } = useFieldArray({ control: form.control, name: 'splits' })
  const splitType = form.watch('split_type')
  const amount = parseFloat(form.watch('amount') || '0')

  const createExpense = useCreateExpense(groupId)
  const updateExpense = useUpdateExpense(groupId, expense?.id ?? 0)

  const toggleParticipant = (userId: number) => {
    const idx = fields.findIndex(f => f.user_id === userId)
    if (idx >= 0) { remove(idx) } else { append({ user_id: userId, amount: '', percentage: '', shares: '' }) }
  }

  const isParticipant = (userId: number) => fields.some(f => f.user_id === userId)

  // Live preview for equal split
  const equalShare = fields.length > 0 ? (amount / fields.length) : 0

  // Percentage preview
  const totalPct = fields.reduce((a, _, i) => a + parseFloat(form.watch(`splits.${i}.percentage`) || '0'), 0)

  // Shares preview
  const totalShares = fields.reduce((a, _, i) => a + parseFloat(form.watch(`splits.${i}.shares`) || '0'), 0)

  const onSubmit = async (data: ExpenseFormData) => {
    const payload = {
      ...data,
      paid_by: data.paid_by,
      splits: data.splits.map(s => ({
        user_id: s.user_id,
        ...(data.split_type === 'unequal' && { amount: s.amount }),
        ...(data.split_type === 'percentage' && { percentage: s.percentage }),
        ...(data.split_type === 'shares' && { shares: s.shares }),
      })),
    }
    if (expense) {
      await updateExpense.mutateAsync(payload)
    } else {
      await createExpense.mutateAsync(payload)
    }
    onClose()
  }

  const isPending = createExpense.isPending || updateExpense.isPending
  const errors = form.formState.errors

  return (
    <Modal open={open} onClose={onClose} title={title} className="max-w-xl">
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input label="Description" placeholder="e.g. Dinner at restaurant" error={errors.description?.message}
          {...form.register('description')} />

        <div className="grid grid-cols-2 gap-3">
          <Input label="Amount (₹)" type="number" step="0.01" min="0.01"
            placeholder="0.00" error={errors.amount?.message} {...form.register('amount')} />
          <Controller control={form.control} name="category" render={({ field }) => (
            <Select label="Category" {...field}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
            </Select>
          )} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input label="Date" type="date" error={errors.expense_date?.message} {...form.register('expense_date')} />
          <Controller control={form.control} name="split_type" render={({ field }) => (
            <Select label="Split type" {...field}>
              {SPLIT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </Select>
          )} />
        </div>

        <Controller control={form.control} name="paid_by" render={({ field }) => (
          <Select label="Paid by" value={field.value?.toString() ?? ''} onChange={e => field.onChange(parseInt(e.target.value))}>
            <option value="">Select payer</option>
            {activeMembers.map(m => (
              <option key={m.user.id} value={m.user.id}>{m.user.first_name} {m.user.last_name}</option>
            ))}
          </Select>
        )} />

        {/* Participant selector */}
        <div>
          <p className="text-sm font-medium text-zinc-300 mb-2">Participants</p>
          <div className="flex flex-wrap gap-2">
            {activeMembers.map(m => (
              <button key={m.user.id} type="button"
                onClick={() => toggleParticipant(m.user.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border transition-all ${
                  isParticipant(m.user.id)
                    ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300'
                    : 'border-white/10 text-zinc-400 hover:border-white/20'
                }`}>
                {isParticipant(m.user.id) && <Check className="size-3" />}
                {m.user.first_name}
              </button>
            ))}
          </div>
        </div>

        {/* Split inputs */}
        {fields.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-zinc-300">Split breakdown</p>
              {splitType === 'equal' && amount > 0 && (
                <Badge variant="default">₹{equalShare.toFixed(2)} each</Badge>
              )}
              {splitType === 'percentage' && (
                <Badge variant={Math.abs(totalPct - 100) < 0.01 ? 'success' : 'warning'}>{totalPct.toFixed(1)}%</Badge>
              )}
            </div>
            {splitType !== 'equal' && fields.map((field, i) => {
              const member = activeMembers.find(m => m.user.id === field.user_id)
              return (
                <div key={field.id} className="flex items-center gap-3 p-2 bg-surface-2 rounded-lg">
                  <p className="text-sm text-white flex-1">{member?.user.first_name ?? 'Unknown'}</p>
                  {splitType === 'unequal' && (
                    <div className="flex items-center gap-1">
                      <span className="text-zinc-500 text-sm">₹</span>
                      <input type="number" step="0.01" min="0" className="w-24 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="0.00" {...form.register(`splits.${i}.amount`)} />
                    </div>
                  )}
                  {splitType === 'percentage' && (
                    <div className="flex items-center gap-1">
                      <input type="number" step="0.01" min="0" max="100" className="w-20 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="0" {...form.register(`splits.${i}.percentage`)} />
                      <span className="text-zinc-500 text-sm">%</span>
                      {amount > 0 && (
                        <span className="text-xs text-zinc-500 ml-1">
                          = ₹{(amount * parseFloat(form.watch(`splits.${i}.percentage`) || '0') / 100).toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}
                  {splitType === 'shares' && (
                    <div className="flex items-center gap-1">
                      <input type="number" step="1" min="0" className="w-20 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="1" {...form.register(`splits.${i}.shares`)} />
                      <span className="text-zinc-500 text-sm">shares</span>
                      {amount > 0 && totalShares > 0 && (
                        <span className="text-xs text-zinc-500 ml-1">
                          = ₹{(amount * parseFloat(form.watch(`splits.${i}.shares`) || '0') / totalShares).toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {errors.splits && <p className="text-xs text-rose-400">{errors.splits.message ?? errors.splits.root?.message}</p>}

        <div className="flex gap-3 justify-end pt-2">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>{expense ? 'Update Expense' : 'Add Expense'}</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Record Settlement ────────────────────────────────────────────────

const settlementSchema = z.object({
  payer_id: z.string().refine(v => v !== '', 'Select payer'),
  receiver_id: z.string().refine(v => v !== '', 'Select receiver'),
  amount: z.string().refine(v => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Amount must be > 0'),
  note: z.string().optional(),
}).refine(d => d.payer_id !== d.receiver_id, { message: 'Payer and receiver must be different', path: ['receiver_id'] })

type SettlementForm = z.infer<typeof settlementSchema>

function RecordSettlementModal({ open, onClose, groupId, members }: {
  open: boolean; onClose: () => void; groupId: number; members: GroupMember[]
}) {
  const { register, handleSubmit, formState: { errors }, reset } = useForm<SettlementForm>({
    resolver: zodResolver(settlementSchema),
  })
  const create = useCreateSettlement(groupId)
  const activeMembers = members.filter(m => m.is_active)

  const onSubmit = async (data: SettlementForm) => {
    await create.mutateAsync({ payer_id: parseInt(data.payer_id), receiver_id: parseInt(data.receiver_id), amount: data.amount, note: data.note })
    reset(); onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Record Settlement">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Select label="Payer (who paid)" error={errors.payer_id?.message} {...register('payer_id')}>
          <option value="">Select payer</option>
          {activeMembers.map(m => <option key={m.user.id} value={m.user.id}>{m.user.first_name} {m.user.last_name}</option>)}
        </Select>
        <Select label="Receiver (who received)" error={errors.receiver_id?.message} {...register('receiver_id')}>
          <option value="">Select receiver</option>
          {activeMembers.map(m => <option key={m.user.id} value={m.user.id}>{m.user.first_name} {m.user.last_name}</option>)}
        </Select>
        <Input label="Amount (₹)" type="number" step="0.01" min="0.01" placeholder="0.00" error={errors.amount?.message} {...register('amount')} />
        <Textarea label="Note (optional)" placeholder="What was this for?" rows={2} {...register('note')} />
        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Record Settlement</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Modal Manager (renders active modal) ────────────────────────────

export function ModalManager() {
  const { activeModal, modalProps, closeModal } = useUIStore()
  const groupId = (modalProps.groupId as number) ?? 0
  const { data: membersData } = useGroupMembers(groupId)
  const members = membersData ?? []

  return (
    <>
      <CreateGroupModal open={activeModal === 'create_group'} onClose={closeModal} />
      <InviteMemberModal open={activeModal === 'invite_member'} onClose={closeModal} groupId={groupId} />
      <ExpenseFormModal
        open={activeModal === 'add_expense'} onClose={closeModal}
        groupId={groupId} members={members} title="Add Expense" />
      <ExpenseFormModal
        open={activeModal === 'edit_expense'} onClose={closeModal}
        groupId={groupId} members={members}
        expense={modalProps.expense as Expense} title="Edit Expense" />
      <RecordSettlementModal
        open={activeModal === 'record_settlement'} onClose={closeModal}
        groupId={groupId} members={members} />
    </>
  )
}
