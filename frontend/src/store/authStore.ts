import { create } from 'zustand'
import type { User } from '../types'

interface AuthState {
  user: User | null
  accessToken: string | null
  isHydrated: boolean
  login: (tokens: { access: string; refresh: string }, user: User) => void
  logout: () => void
  setAccessToken: (token: string) => void
  setUser: (user: User) => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  isHydrated: false,

  login: ({ access, refresh }, user) => {
    localStorage.setItem('refresh_token', refresh)
    set({ accessToken: access, user, isHydrated: true })
  },

  logout: () => {
    localStorage.removeItem('refresh_token')
    set({ user: null, accessToken: null })
    window.location.href = '/login'
  },

  setAccessToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),

  hydrate: async () => {
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) { set({ isHydrated: true }); return }
    try {
      const { default: axios } = await import('axios')
      const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
      const { data: tokens } = await axios.post(`${base}/api/auth/token/refresh/`, { refresh })
      set({ accessToken: tokens.access })
      const { default: api } = await import('../lib/axios')
      const { data: user } = await api.get('/api/auth/me/')
      set({ user, isHydrated: true })
    } catch {
      localStorage.removeItem('refresh_token')
      set({ isHydrated: true })
    }
  },
}))
