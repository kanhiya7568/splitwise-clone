export interface User { id: number; email: string; first_name: string; last_name: string }
export interface Group { id: number; name: string; created_by: User; member_count?: number; created_at: string; members?: GroupMember[] }
export interface GroupMember { id: number; user: User; role: 'admin' | 'member'; is_active: boolean }
export interface ExpenseSplit { id: number; user: User; amount: string; percentage?: string; shares?: string }
export interface Expense {
  id: number; description: string; amount: string; category: string; category_display: string
  expense_date: string; split_type: string; split_type_display: string
  paid_by: User; created_by: User; splits: ExpenseSplit[]
  created_at: string; updated_at: string; is_deleted: boolean
}
export interface Balance { user1: User; user2: User; net_amount: string; group?: { id: number; name: string } }
export interface SimplifiedBalance { payer: User; receiver: User; amount: string }
export interface Settlement { id: number; payer: User; receiver: User; amount: string; note: string; created_at: string; is_deleted: boolean; group: number }
export interface Message { id: number; sender: User; content: string; is_deleted: boolean; created_at: string; expense: number }
export interface TokenPair { access: string; refresh: string }
export interface PaginatedResponse<T> { count: number; next: string | null; previous: string | null; results: T[] }
export type SplitType = 'equal' | 'unequal' | 'percentage' | 'shares'
export type ModalName = 'create_group' | 'invite_member' | 'add_expense' | 'edit_expense' | 'record_settlement' | 'confirm_delete'
export interface BalanceInfo { label: string; amount: number; type: 'receivable' | 'owe' | 'other' }
