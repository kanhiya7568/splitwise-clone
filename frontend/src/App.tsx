import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { queryClient } from './lib/queryClient'
import { useAuthStore } from './store/authStore'
import { AppLayout } from './components/layout/AppLayout'
import { RequireAuth, PublicOnly } from './components/layout/RequireAuth'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { DashboardPage } from './pages/DashboardPage'
import { GroupsPage } from './pages/GroupsPage'
import { GroupDetailPage } from './pages/GroupDetailPage'
import { ExpenseDetailPage } from './pages/ExpenseDetailPage'
import { BalancesPage } from './pages/BalancesPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ImportPage } from './pages/ImportPage'

function AppContent() {
  const hydrate = useAuthStore(s => s.hydrate)
  useEffect(() => { hydrate() }, [hydrate])
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="groups" element={<GroupsPage />} />
            <Route path="groups/:groupId" element={<GroupDetailPage />} />
            <Route path="groups/:groupId/expenses/:expenseId" element={<ExpenseDetailPage />} />
            <Route path="balances" element={<BalancesPage />} />
            <Route path="import" element={<ImportPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
      <Toaster position="bottom-right" richColors theme="dark" />
    </QueryClientProvider>
  )
}
