import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Balance, BalanceInfo, User } from '../types'

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }

export function getInitials(user: User): string {
  return `${user.first_name[0] ?? ''}${user.last_name[0] ?? ''}`.toUpperCase()
}

export function formatCurrency(amount: string | number): string {
  const n = typeof amount === 'string' ? parseFloat(amount) : amount
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(n)
}

export function formatDate(d: string): string {
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatTime(d: string): string {
  return new Date(d).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export function resolveBalance(balance: Balance, currentUserId: number): BalanceInfo {
  const net = parseFloat(balance.net_amount)
  const abs = Math.abs(net)
  // net > 0: user2 owes user1; net < 0: user1 owes user2
  const creditor = net > 0 ? balance.user1 : balance.user2
  const debtor = net > 0 ? balance.user2 : balance.user1
  if (abs < 0.01) return { label: 'Settled', amount: 0, type: 'other' }
  if (currentUserId === creditor.id) return { label: `${debtor.first_name} owes you`, amount: abs, type: 'receivable' }
  if (currentUserId === debtor.id) return { label: `You owe ${creditor.first_name}`, amount: abs, type: 'owe' }
  return { label: `${debtor.first_name} owes ${creditor.first_name}`, amount: abs, type: 'other' }
}

export function avatarColor(id: number): string {
  const colors = ['bg-indigo-500','bg-violet-500','bg-pink-500','bg-rose-500','bg-orange-500','bg-teal-500','bg-cyan-500','bg-emerald-500']
  return colors[id % colors.length]
}

export const CATEGORIES = ['food','transport','accommodation','entertainment','utilities','other','general'] as const
export const SPLIT_TYPES: { value: string; label: string }[] = [
  { value: 'equal', label: 'Equal' },
  { value: 'unequal', label: 'Unequal' },
  { value: 'percentage', label: 'Percentage' },
  { value: 'shares', label: 'Shares' },
]
