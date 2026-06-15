import React from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, Wallet, LogOut, DollarSign, Upload } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useUIStore } from '../../store/uiStore'
import { useLogout } from '../../hooks'
import { Avatar, Button } from '../ui'
import { cn } from '../../lib/utils'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/groups', icon: Users, label: 'Groups' },
  { to: '/balances', icon: Wallet, label: 'Balances' },
  { to: '/import', icon: Upload, label: 'Import CSV' },
] as const

function NavItem({ to, icon: Icon, label }: { to: string; icon: React.ElementType; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
          isActive
            ? 'bg-indigo-500/15 text-indigo-300'
            : 'text-zinc-400 hover:text-white hover:bg-white/5'
        )
      }
    >
      <Icon className="size-4 shrink-0" />
      {label}
    </NavLink>
  )
}

export function Sidebar({ mobile = false }: { mobile?: boolean }) {
  const user = useAuthStore(s => s.user)
  const logout = useLogout()
  const { setSidebarOpen } = useUIStore()

  return (
    <div className={cn('flex flex-col h-full', mobile && 'px-3 py-2')}>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3 py-5 mb-1">
        <div className="size-8 bg-indigo-600 rounded-xl flex items-center justify-center shrink-0">
          <DollarSign className="size-4 text-white" />
        </div>
        <span className="font-bold text-white tracking-tight">Splitwise</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2">
        {NAV.map(n => <NavItem key={n.to} {...n} />)}
      </nav>

      {/* User section */}
      {user && (
        <div className="border-t border-white/8 pt-3 mt-3 px-2 pb-3">
          <div className="flex items-center gap-3 px-2 py-1.5 mb-1">
            <Avatar user={user} size="sm" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {user.first_name} {user.last_name}
              </p>
              <p className="text-xs text-zinc-500 truncate">{user.email}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-zinc-400 hover:text-white"
            onClick={() => {
              logout.mutate()
              if (mobile) setSidebarOpen(false)
            }}
          >
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      )}
    </div>
  )
}
