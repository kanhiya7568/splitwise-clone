import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { Spinner } from '../ui'

export function RequireAuth() {
  const { user, isHydrated } = useAuthStore()
  const location = useLocation()
  if (!isHydrated) return (
    <div className="flex h-screen items-center justify-center">
      <Spinner className="size-8 text-indigo-400" />
    </div>
  )
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return <Outlet />
}

export function PublicOnly() {
  const { user, isHydrated } = useAuthStore()
  if (!isHydrated) return null
  if (user) return <Navigate to="/" replace />
  return <Outlet />
}
