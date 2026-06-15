import React from 'react'
import { cn, avatarColor, getInitials } from '../../lib/utils'
import type { User } from '../../types'

// ── Button ────────────────────────────────────────────────────────────
interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'destructive' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}
export const Button = React.forwardRef<HTMLButtonElement, BtnProps>(
  ({ variant = 'primary', size = 'md', loading, className, children, disabled, ...p }, ref) => {
    const base = 'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-50 disabled:cursor-not-allowed'
    const variants = {
      primary: 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm',
      ghost: 'hover:bg-white/5 text-zinc-300 hover:text-white',
      destructive: 'bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/20',
      outline: 'border border-white/10 hover:bg-white/5 text-zinc-300',
    }
    const sizes = { sm: 'text-sm px-3 py-1.5', md: 'text-sm px-4 py-2', lg: 'text-base px-5 py-2.5' }
    return (
      <button ref={ref} disabled={disabled || loading} className={cn(base, variants[variant], sizes[size], className)} {...p}>
        {loading && <Spinner className="size-4" />}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'

// ── Input ─────────────────────────────────────────────────────────────
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { error?: string; label?: string }
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ error, label, className, id, ...p }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={id} className="text-sm font-medium text-zinc-300">{label}</label>}
      <input
        ref={ref} id={id}
        className={cn('w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all', error && 'border-rose-500/50 focus:ring-rose-500', className)}
        {...p}
      />
      {error && <p className="text-xs text-rose-400">{error}</p>}
    </div>
  )
)
Input.displayName = 'Input'

// ── Textarea ──────────────────────────────────────────────────────────
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> { error?: string; label?: string }
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ error, label, className, id, ...p }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={id} className="text-sm font-medium text-zinc-300">{label}</label>}
      <textarea
        ref={ref} id={id}
        className={cn('w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none transition-all', error && 'border-rose-500/50', className)}
        {...p}
      />
      {error && <p className="text-xs text-rose-400">{error}</p>}
    </div>
  )
)
Textarea.displayName = 'Textarea'

// ── Select ────────────────────────────────────────────────────────────
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> { error?: string; label?: string }
export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ error, label, className, id, children, ...p }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={id} className="text-sm font-medium text-zinc-300">{label}</label>}
      <select
        ref={ref} id={id}
        className={cn('w-full bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer transition-all', error && 'border-rose-500/50', className)}
        {...p}
      >
        {children}
      </select>
      {error && <p className="text-xs text-rose-400">{error}</p>}
    </div>
  )
)
Select.displayName = 'Select'

// ── Card ──────────────────────────────────────────────────────────────
export const Card = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('bg-surface-1 border border-white/8 rounded-xl', className)} {...props}>{children}</div>
)

// ── Avatar ────────────────────────────────────────────────────────────
export const Avatar = ({ user, size = 'md', className }: { user: User; size?: 'sm' | 'md' | 'lg'; className?: string }) => {
  const sizes = { sm: 'size-7 text-xs', md: 'size-9 text-sm', lg: 'size-12 text-base' }
  return (
    <div className={cn('rounded-full flex items-center justify-center font-semibold text-white shrink-0', avatarColor(user.id), sizes[size], className)}>
      {getInitials(user)}
    </div>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────
export const Badge = ({ children, variant = 'default', className }: { children: React.ReactNode; variant?: 'default' | 'success' | 'error' | 'warning'; className?: string }) => {
  const variants = {
    default: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20',
    success: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
    error: 'bg-rose-500/10 text-rose-300 border-rose-500/20',
    warning: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  }
  return <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border', variants[variant], className)}>{children}</span>
}

// ── Spinner ───────────────────────────────────────────────────────────
export const Spinner = ({ className }: { className?: string }) => (
  <svg className={cn('animate-spin', className ?? 'size-5')} fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
)

// ── Skeleton ──────────────────────────────────────────────────────────
export const Skeleton = ({ className }: { className?: string }) => (
  <div className={cn('animate-pulse bg-white/5 rounded-lg', className)} />
)

// ── Empty State ───────────────────────────────────────────────────────
export const EmptyState = ({ icon, title, description, action }: {
  icon: React.ReactNode; title: string; description?: string; action?: React.ReactNode
}) => (
  <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
    <div className="size-14 rounded-2xl bg-white/5 flex items-center justify-center text-zinc-400">{icon}</div>
    <div>
      <p className="text-white font-medium">{title}</p>
      {description && <p className="text-sm text-zinc-500 mt-1">{description}</p>}
    </div>
    {action}
  </div>
)

// ── Modal ─────────────────────────────────────────────────────────────
export const Modal = ({ open, onClose, title, children, className }: {
  open: boolean; onClose: () => void; title?: string; children: React.ReactNode; className?: string
}) => {
  React.useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className={cn('relative bg-surface-1 border border-white/10 rounded-2xl shadow-2xl w-full max-w-lg animate-slide-up max-h-[90vh] overflow-y-auto', className)}>
        {title && (
          <div className="flex items-center justify-between p-6 pb-0">
            <h2 className="text-lg font-semibold text-white">{title}</h2>
          </div>
        )}
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

// ── StatCard ──────────────────────────────────────────────────────────
export const StatCard = ({ label, value, sub, color = 'default' }: { label: string; value: string; sub?: string; color?: 'default' | 'green' | 'red' }) => {
  const colors = { default: 'text-white', green: 'text-emerald-400', red: 'text-rose-400' }
  return (
    <Card className="p-5">
      <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">{label}</p>
      <p className={cn('text-2xl font-bold', colors[color])}>{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
    </Card>
  )
}
