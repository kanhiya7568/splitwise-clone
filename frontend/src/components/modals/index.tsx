// Modals container
import { useForm, useFieldArray, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Check } from 'lucide-react'
import { Modal, Button, Input, Select, Textarea, Badge } from '../ui'
import { useUIStore } from '../../store/uiStore'
import {
  useCreateGroup,
  useInviteMember,
  useCreateExpense,
  useUpdateExpense,
  useCreateSettlement,
  useGroupMembers,
} from '../../hooks'
import { formatCurrency, CATEGORIES, SPLIT_TYPES } from '../../lib/utils'
import type { Expense, GroupMember } from '../../types'

// ─── Create Group ─────────────────────────────────────────────────────
const createGroupSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
})
type CreateGroupForm = z.infer<typeof createGroupSchema>

function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const form = useForm<CreateGroupForm>({ resolver: zodResolver(createGroupSchema) })
  const create = useCreateGroup()

  const onSubmit = async (data: CreateGroupForm) => {
    await create.mutateAsync(data.name)
    form.reset()
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Create Group">
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input
          label="Group name"
          placeholder="e.g. Goa Trip 2024"
          error={form.formState.errors.name?.message}
          {...form.register('name')}
        />
        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Create Group</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Invite Member ────────────────────────────────────────────────────
const inviteSchema = z.object({ email: z.string().email('Enter a valid email') })
type InviteForm = z.infer<typeof inviteSchema>

function InviteMemberModal({
  open, onClose, groupId,
}: { open: boolean; onClose: () => void; groupId: number }) {
  const form = useForm<InviteForm>({ resolver: zodResolver(inviteSchema) })
  const invite = useInviteMember(groupId)

  const onSubmit = async (data: InviteForm) => {
    await invite.mutateAsync(data.email)
    form.reset()
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Invite Member">
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Input
          label="Email address"
          type="email"
          placeholder="friend@example.com"
          error={form.formState.errors.email?.message}
          {...form.register('email')}
        />
        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={invite.isPending}>Send Invite</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Expense Form (Add + Edit) ────────────────────────────────────────
const splitEntrySchema = z.object({
  user_id: z.number(),
  amount: z.string().optional(),
  percentage: z.string().optional(),
  shares: z.string().optional(),
})

const expenseSchema = z
  .object({
    description: z.string().min(1, 'Description required'),
    amount: z
      .string()
      .refine(v => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Amount must be positive'),
    category: z.string().default('general'),
    expense_date: z.string().min(1, 'Date required'),
    split_type: z.enum(['equal', 'unequal', 'percentage', 'shares']),
    paid_by: z.number({ required_error: 'Select a payer' }).optional(),
    splits: z.array(splitEntrySchema).min(1, 'Add at least one participant'),
  })
  .superRefine((data, ctx) => {
    const total = parseFloat(data.amount)
    if (isNaN(total)) return
    if (data.split_type === 'unequal') {
      const sum = data.splits.reduce((a, s) => a + parseFloat(s.amount ?? '0'), 0)
      if (Math.abs(sum - total) > 0.01)
        ctx.addIssue({
          code: 'custom',
          path: ['splits'],
          message: `Amounts must sum to ${formatCurrency(total)} (currently ${formatCurrency(sum)})`,
        })
    }
    if (data.split_type === 'percentage') {
      const sum = data.splits.reduce((a, s) => a + parseFloat(s.percentage ?? '0'), 0)
      if (Math.abs(sum - 100) > 0.01)
        ctx.addIssue({
          code: 'custom',
          path: ['splits'],
          message: `Percentages must sum to 100% (currently ${sum.toFixed(2)}%)`,
        })
    }
    if (data.split_type === 'shares') {
      const sum = data.splits.reduce((a, s) => a + parseFloat(s.shares ?? '0'), 0)
      if (sum <= 0)
        ctx.addIssue({ code: 'custom', path: ['splits'], message: 'Total shares must be > 0' })
    }
  })

type ExpenseFormData = z.infer<typeof expenseSchema>

function ExpenseFormModal({
  open, onClose, groupId, members, expense, title,
}: {
  open: boolean
  onClose: () => void
  groupId: number
  members: GroupMember[]
  expense?: Expense
  title: string
}) {
  const today = new Date().toISOString().split('T')[0]
  const activeMembers = members.filter(m => m.is_active)

  const form = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseSchema),
    defaultValues: expense
      ? {
          description: expense.description,
          amount: expense.amount,
          category: expense.category,
          expense_date: expense.expense_date,
          split_type: expense.split_type as ExpenseFormData['split_type'],
          paid_by: expense.paid_by.id,
          splits: expense.splits.map(s => ({
            user_id: s.user.id,
            amount: s.amount,
            percentage: s.percentage ?? '',
            shares: s.shares ?? '',
          })),
        }
      : {
          description: '',
          amount: '',
          category: 'general',
          expense_date: today,
          split_type: 'equal',
          splits: [],
        },
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: 'splits',
  })

  const splitType = form.watch('split_type')
  const amountStr = form.watch('amount')
  const amount = parseFloat(amountStr || '0')

  const createExpense = useCreateExpense(groupId)
  const updateExpense = useUpdateExpense(groupId, expense?.id ?? 0)

  const isParticipant = (userId: number) => fields.some(f => f.user_id === userId)

  const toggleParticipant = (userId: number) => {
    const idx = fields.findIndex(f => f.user_id === userId)
    if (idx >= 0) {
      remove(idx)
    } else {
      append({ user_id: userId, amount: '', percentage: '', shares: '' })
    }
  }

  // Live calculations
  const equalShare = fields.length > 0 && amount > 0 ? amount / fields.length : 0
  const totalPct = fields.reduce(
    (a, _, i) => a + parseFloat(form.watch(`splits.${i}.percentage`) || '0'),
    0
  )
  const totalShares = fields.reduce(
    (a, _, i) => a + parseFloat(form.watch(`splits.${i}.shares`) || '0'),
    0
  )

  const onSubmit = async (data: ExpenseFormData) => {
    const payload = {
      description: data.description,
      amount: data.amount,
      category: data.category,
      expense_date: data.expense_date,
      split_type: data.split_type,
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
    form.reset()
    onClose()
  }

  const isPending = createExpense.isPending || updateExpense.isPending
  const { errors } = form.formState

  return (
    <Modal open={open} onClose={onClose} title={title} className="max-w-xl">
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        {/* Description */}
        <Input
          label="Description"
          placeholder="e.g. Dinner at restaurant"
          error={errors.description?.message}
          {...form.register('description')}
        />

        {/* Amount + Category */}
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Amount (₹)"
            type="number"
            step="0.01"
            min="0.01"
            placeholder="0.00"
            error={errors.amount?.message}
            {...form.register('amount')}
          />
          <Controller
            control={form.control}
            name="category"
            render={({ field }) => (
              <Select label="Category" {...field}>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </Select>
            )}
          />
        </div>

        {/* Date + Split type */}
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Date"
            type="date"
            error={errors.expense_date?.message}
            {...form.register('expense_date')}
          />
          <Controller
            control={form.control}
            name="split_type"
            render={({ field }) => (
              <Select label="Split type" {...field}>
                {SPLIT_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </Select>
            )}
          />
        </div>

        {/* Paid by */}
        <Controller
          control={form.control}
          name="paid_by"
          render={({ field }) => (
            <Select
              label="Paid by"
              value={field.value?.toString() ?? ''}
              onChange={e => field.onChange(parseInt(e.target.value))}
            >
              <option value="">Select payer</option>
              {activeMembers.map(m => (
                <option key={m.user.id} value={m.user.id}>
                  {m.user.first_name} {m.user.last_name}
                </option>
              ))}
            </Select>
          )}
        />

        {/* Participants */}
        <div>
          <p className="text-sm font-medium text-zinc-300 mb-2">
            Participants
            {splitType === 'equal' && equalShare > 0 && (
              <Badge variant="default" className="ml-2">₹{equalShare.toFixed(2)} each</Badge>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {activeMembers.map(m => (
              <button
                key={m.user.id}
                type="button"
                onClick={() => toggleParticipant(m.user.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm border transition-all ${
                  isParticipant(m.user.id)
                    ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300'
                    : 'border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-300'
                }`}
              >
                {isParticipant(m.user.id) && <Check className="size-3" />}
                {m.user.first_name}
              </button>
            ))}
          </div>
        </div>

        {/* Split inputs (unequal / percentage / shares) */}
        {fields.length > 0 && splitType !== 'equal' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-zinc-300">Split breakdown</p>
              {splitType === 'percentage' && (
                <Badge variant={Math.abs(totalPct - 100) < 0.01 ? 'success' : 'warning'}>
                  {totalPct.toFixed(1)}% / 100%
                </Badge>
              )}
              {splitType === 'shares' && totalShares > 0 && amount > 0 && (
                <Badge variant="default">{totalShares} shares total</Badge>
              )}
            </div>
            {fields.map((field, i) => {
              const member = activeMembers.find(m => m.user.id === field.user_id)
              const sharesVal = parseFloat(form.watch(`splits.${i}.shares`) || '0')
              const pctVal = parseFloat(form.watch(`splits.${i}.percentage`) || '0')

              return (
                <div key={field.id} className="flex items-center gap-3 p-3 bg-surface-2 rounded-xl border border-white/5">
                  <p className="text-sm text-white flex-1 min-w-0 truncate">
                    {member?.user.first_name ?? 'Unknown'}
                  </p>

                  {splitType === 'unequal' && (
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-zinc-500 text-sm">₹</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        className="w-24 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="0.00"
                        {...form.register(`splits.${i}.amount`)}
                      />
                    </div>
                  )}

                  {splitType === 'percentage' && (
                    <div className="flex items-center gap-1 shrink-0">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        className="w-16 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="0"
                        {...form.register(`splits.${i}.percentage`)}
                      />
                      <span className="text-zinc-500 text-sm">%</span>
                      {amount > 0 && (
                        <span className="text-xs text-zinc-500 ml-1 w-16 text-right">
                          = ₹{(amount * pctVal / 100).toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}

                  {splitType === 'shares' && (
                    <div className="flex items-center gap-1 shrink-0">
                      <input
                        type="number"
                        step="1"
                        min="0"
                        className="w-16 bg-transparent text-sm text-white text-right focus:outline-none"
                        placeholder="1"
                        {...form.register(`splits.${i}.shares`)}
                      />
                      <span className="text-zinc-500 text-sm">sh</span>
                      {amount > 0 && totalShares > 0 && (
                        <span className="text-xs text-zinc-500 ml-1 w-16 text-right">
                          = ₹{(amount * sharesVal / totalShares).toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Validation errors for splits array */}
        {errors.splits && !Array.isArray(errors.splits) && (
          <p className="text-xs text-rose-400">
            {(errors.splits as { message?: string }).message}
          </p>
        )}

        <div className="flex gap-3 justify-end pt-1">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>
            {expense ? 'Update Expense' : 'Add Expense'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Record Settlement ────────────────────────────────────────────────
const settlementSchema = z
  .object({
    payer_id: z.string().min(1, 'Select payer'),
    receiver_id: z.string().min(1, 'Select receiver'),
    amount: z
      .string()
      .refine(v => !isNaN(parseFloat(v)) && parseFloat(v) > 0, 'Amount must be positive'),
    note: z.string().optional(),
  })
  .refine(d => d.payer_id !== d.receiver_id, {
    message: 'Payer and receiver must be different',
    path: ['receiver_id'],
  })

type SettlementFormData = z.infer<typeof settlementSchema>

function RecordSettlementModal({
  open, onClose, groupId, members,
}: {
  open: boolean
  onClose: () => void
  groupId: number
  members: GroupMember[]
}) {
  const form = useForm<SettlementFormData>({ resolver: zodResolver(settlementSchema) })
  const create = useCreateSettlement(groupId)
  const activeMembers = members.filter(m => m.is_active)

  const onSubmit = async (data: SettlementFormData) => {
    await create.mutateAsync({
      payer_id: parseInt(data.payer_id),
      receiver_id: parseInt(data.receiver_id),
      amount: data.amount,
      note: data.note,
    })
    form.reset()
    onClose()
  }

  const { errors } = form.formState

  return (
    <Modal open={open} onClose={onClose} title="Record Settlement">
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Select label="Payer (who paid)" error={errors.payer_id?.message} {...form.register('payer_id')}>
          <option value="">Select payer</option>
          {activeMembers.map(m => (
            <option key={m.user.id} value={m.user.id}>
              {m.user.first_name} {m.user.last_name}
            </option>
          ))}
        </Select>

        <Select label="Receiver (who got paid)" error={errors.receiver_id?.message} {...form.register('receiver_id')}>
          <option value="">Select receiver</option>
          {activeMembers.map(m => (
            <option key={m.user.id} value={m.user.id}>
              {m.user.first_name} {m.user.last_name}
            </option>
          ))}
        </Select>

        <Input
          label="Amount (₹)"
          type="number"
          step="0.01"
          min="0.01"
          placeholder="0.00"
          error={errors.amount?.message}
          {...form.register('amount')}
        />

        <Textarea
          label="Note (optional)"
          placeholder="What was this for?"
          rows={2}
          {...form.register('note')}
        />

        <div className="flex gap-3 justify-end">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={create.isPending}>Record Settlement</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Modal Manager ────────────────────────────────────────────────────
export function ModalManager() {
  const { activeModal, modalProps, closeModal } = useUIStore()
  const groupId = (modalProps.groupId as number) ?? 0
  const { data: membersData } = useGroupMembers(groupId)
  const members = membersData ?? []

  return (
    <>
      <CreateGroupModal
        open={activeModal === 'create_group'}
        onClose={closeModal}
      />
      <InviteMemberModal
        open={activeModal === 'invite_member'}
        onClose={closeModal}
        groupId={groupId}
      />
      <ExpenseFormModal
        open={activeModal === 'add_expense'}
        onClose={closeModal}
        groupId={groupId}
        members={members}
        title="Add Expense"
      />
      <ExpenseFormModal
        open={activeModal === 'edit_expense'}
        onClose={closeModal}
        groupId={groupId}
        members={members}
        expense={modalProps.expense as Expense | undefined}
        title="Edit Expense"
      />
      <RecordSettlementModal
        open={activeModal === 'record_settlement'}
        onClose={closeModal}
        groupId={groupId}
        members={members}
      />
    </>
  )
}
